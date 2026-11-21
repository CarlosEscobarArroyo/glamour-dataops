"""Extrae las 18 tablas comerciales seleccionadas y guarda sus datos crudos en GCS."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

from google.cloud import storage
import pyarrow as pa
import pyarrow.parquet as pq
import pymysql


# Las pone el Job (src/extraction/job.yaml); MYSQL_PASSWORD llega desde Secret Manager.
VARIABLES = (
    "GCS_BUCKET", "MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD",
    "MYSQL_DATABASE", "MYSQL_PORT",
)

BATCH_SIZE = 50000  # filas por lote; limita la memoria usada por tabla

TABLAS = (
    "persona",
    "contenido",
    "campana",
    "documento",
    "documentodetalle",
    "stockcontrol",
    "stockmovi",
    "stocknotas",
    "contenidoprenda",
    "campanarangos",
    "sventas",
    "personasaldos",
    "webparametros",
    "webmodulos",
    "pagepagos",
    "seccion",
    "seccioncontenido",
    "documentofile",
)
# Se exportan como texto SQL: el origen contiene fechas cero (0000-00-00) y TIME
# fuera de 24 horas que Arrow no representa. La capa analítica las convierte.
TEMPORALES = {"date", "datetime", "timestamp", "time"}


def log_event(event: str, severity: str = "INFO", **fields) -> None:
    print(json.dumps({"severity": severity, "event": event, **fields}), flush=True)


def conectar_mysql():
    try:
        return pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            port=int(os.environ["MYSQL_PORT"]),
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=300,
            autocommit=True,
        )
    except (pymysql.MySQLError, ValueError) as error:
        # Un error de conexión no contiene filas ni la contraseña.
        log_event("mysql_connection_failed", "ERROR", message=str(error))
        raise


def quoted(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def arrow_type(data_type: str, column_type: str, precision, scale):
    """Usa el esquema SQL para conservar tipos incluso con lotes vacíos o NULL."""
    if data_type in {"tinyint", "smallint", "mediumint", "int", "bigint", "year"}:
        if data_type == "bigint" and "unsigned" in column_type.lower():
            return pa.uint64()
        return pa.int64()
    if data_type in {"decimal", "numeric"}:
        decimal = pa.decimal128 if precision <= 38 else pa.decimal256
        return decimal(int(precision), int(scale))
    if data_type == "float":
        return pa.float32()
    if data_type in {"double", "real"}:
        return pa.float64()
    if data_type in TEMPORALES or data_type in {
        "char", "varchar", "tinytext", "text", "mediumtext", "longtext",
        "enum", "set", "json",
    }:
        return pa.string()
    if data_type in {
        "binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob", "bit",
    }:
        return pa.binary()
    raise ValueError(f"Tipo SQL no soportado: {data_type}")


def esquema_tabla(connection, table: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                   NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table,),
        )
        columns = cursor.fetchall()
    if not columns:
        raise ValueError(f"No se encontró el esquema de {table}")

    fields, expressions = [], []
    for name, data_type, column_type, precision, scale, nullable in columns:
        data_type = data_type.lower()
        try:
            dtype = arrow_type(data_type, column_type, precision, scale)
        except ValueError:
            log_event("unsupported_column_type", "ERROR", table=table,
                      column=name, data_type=data_type)
            raise
        fields.append(pa.field(name, dtype, nullable=nullable == "YES"))
        expression = quoted(name)
        if data_type in TEMPORALES:
            expression = f"CAST({expression} AS CHAR) AS {quoted(name)}"
        expressions.append(expression)
    return pa.schema(fields), ", ".join(expressions)


def extraer_tabla(connection, bucket, table: str, run_prefix: str, batch_size: int):
    schema, expressions = esquema_tabla(connection, table)
    objects = []
    total_rows = 0
    with TemporaryDirectory(prefix="glamour-extraction-") as directory:
        path = Path(directory) / "part.parquet"
        # Un cursor sin buffer evita traer toda la tabla a memoria.
        with connection.cursor(pymysql.cursors.SSCursor) as cursor:
            cursor.execute(f"SELECT {expressions} FROM {quoted(table)}")
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows and objects:
                    break
                arrays = [
                    pa.array([row[index] for row in rows], type=field.type)
                    for index, field in enumerate(schema)
                ]
                batch = pa.Table.from_arrays(arrays, schema=schema)
                pq.write_table(batch, path, compression="snappy")
                object_name = f"{run_prefix}/{table}/part-{len(objects):05d}.parquet"
                bucket.blob(object_name).upload_from_filename(
                    str(path), content_type="application/octet-stream",
                    if_generation_match=0,
                )
                objects.append(object_name)
                total_rows += batch.num_rows
                log_event("batch_uploaded", table=table, rows=batch.num_rows,
                          object=object_name)
                # También se publica un Parquet con esquema para tablas vacías.
                if not rows:
                    break

    return {"rows": total_rows, "objects": objects}


def extraer_datos_mysql(connection, bucket, run_prefix: str, batch_size: int):
    results = {}
    log_event("tables_selected", tables=TABLAS)
    # El texto de TIMESTAMP queda en UTC; DATETIME conserva su valor sin zona horaria.
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION time_zone = '+00:00'")
    for table in TABLAS:
        log_event("table_started", table=table)
        results[table] = extraer_tabla(connection, bucket, table, run_prefix, batch_size)

    manifest = {
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "selected_tables",
        "selected_tables": TABLAS,
        "tables": results,
    }
    # Solo existe un manifiesto cuando todas las tablas seleccionadas terminaron.
    bucket.blob(f"{run_prefix}/manifest.json").upload_from_string(
        json.dumps(manifest), content_type="application/json", if_generation_match=0,
    )
    return manifest


def ejecutar_extraccion() -> None:
    bucket = os.environ["GCS_BUCKET"]
    started = datetime.now(timezone.utc)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{uuid4().hex}"
    run_prefix = f"date={started:%Y-%m-%d}/{run_id}"
    log_event("extraction_started", run_id=run_id, bucket=bucket, prefix=run_prefix)

    with storage.Client() as gcs, conectar_mysql() as connection:
        extraer_datos_mysql(connection, gcs.bucket(bucket), run_prefix, BATCH_SIZE)
    log_event("extraction_completed", uri=f"gs://{bucket}/{run_prefix}")


def main() -> int:
    faltan = [name for name in VARIABLES if not os.environ.get(name)]
    if faltan:
        log_event("extraction_failed", "ERROR",
                  message=f"Faltan variables de entorno: {', '.join(faltan)}")
        return 1
    try:
        ejecutar_extraccion()
    except Exception as error:
        # No enviar credenciales ni valores de filas a Cloud Logging.
        log_event("extraction_failed", "ERROR", error_type=type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
