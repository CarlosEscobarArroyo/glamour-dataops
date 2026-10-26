"""Extrae las cinco tablas del ETL legacy y guarda sus datos crudos en GCS."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

import google.auth
from google.cloud import secretmanager, storage
import pyarrow as pa
import pyarrow.parquet as pq
import pymysql


# Mismas tablas y extracción completa que extraer_datos_mysql() del legacy.
TABLAS = ("persona", "contenido", "campana", "documento", "documentodetalle")
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config_dev.json"
MYSQL_SECRET_KEYS = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "MYSQL_PORT")


class ConfigurationError(ValueError):
    """Error de configuración cuyo mensaje no contiene datos ni secretos."""


def cargar_config() -> dict:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        config = {}
    except (OSError, ValueError) as error:
        raise ConfigurationError("No se pudo leer config_dev.json como JSON válido") from error
    for name in ("GOOGLE_CLOUD_PROJECT", "GCS_BUCKET", "GCS_PREFIX", "EXTRACTION_BATCH_SIZE"):
        if name in os.environ:
            config[name] = os.environ[name]
    secret_names = config.setdefault("secrets", {})
    if not isinstance(secret_names, dict):
        raise ConfigurationError("secrets debe ser un objeto con los nombres de los secretos")
    for key in MYSQL_SECRET_KEYS:
        name = secret_names.setdefault(key, key)
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError(f"secrets.{key} debe contener el nombre de un secreto")
    return config


def log_event(event: str, severity: str = "INFO", **fields) -> None:
    print(json.dumps({"severity": severity, "event": event, **fields}), flush=True)


def get_secret(client, project_id: str, secret_name: str) -> str:
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def conectar_mysql(client, project_id: str, secret_names: dict):
    values = {
        key: get_secret(client, project_id, secret_names[key])
        for key in MYSQL_SECRET_KEYS
    }
    return pymysql.connect(
        host=values["MYSQL_HOST"],
        user=values["MYSQL_USER"],
        password=values["MYSQL_PASSWORD"],
        database=values["MYSQL_DATABASE"],
        port=int(values["MYSQL_PORT"]),
        charset="utf8mb4",
        connect_timeout=10,
        read_timeout=300,
        autocommit=True,
    )


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
    if data_type == "date":
        return pa.date32()
    if data_type == "datetime":
        return pa.timestamp("us")
    if data_type == "timestamp":
        return pa.timestamp("us", tz="UTC")
    if data_type in {
        "char", "varchar", "tinytext", "text", "mediumtext", "longtext",
        "enum", "set", "json", "time",
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
        try:
            dtype = arrow_type(data_type.lower(), column_type, precision, scale)
        except ValueError:
            log_event("unsupported_column_type", "ERROR", table=table,
                      column=name, data_type=data_type)
            raise
        fields.append(pa.field(name, dtype, nullable=nullable == "YES"))
        # MariaDB TIME admite duraciones negativas y superiores a 24 horas.
        # Su representación textual conserva esos valores en Parquet.
        expression = quoted(name)
        if data_type.lower() == "time":
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
    # TIMESTAMP se exporta en UTC; DATETIME conserva su valor sin zona horaria.
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION time_zone = '+00:00'")
    for table in TABLAS:
        log_event("table_started", table=table)
        results[table] = extraer_tabla(connection, bucket, table, run_prefix, batch_size)

    manifest = {
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "tables": results,
    }
    # Solo existe un manifiesto cuando las cinco tablas terminaron correctamente.
    bucket.blob(f"{run_prefix}/manifest.json").upload_from_string(
        json.dumps(manifest), content_type="application/json", if_generation_match=0,
    )
    return manifest


def ejecutar_extraccion() -> None:
    config = cargar_config()
    bucket_name = config.get("GCS_BUCKET", "")
    if not isinstance(bucket_name, str):
        raise ConfigurationError("GCS_BUCKET debe ser texto")
    bucket_name = bucket_name.strip()
    if not bucket_name or "/" in bucket_name:
        raise ConfigurationError("Configura GCS_BUCKET con el nombre del bucket, sin gs://")
    try:
        batch_size = int(config.get("EXTRACTION_BATCH_SIZE", 50000))
        task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "EXTRACTION_BATCH_SIZE y CLOUD_RUN_TASK_COUNT deben ser enteros"
        ) from error
    if batch_size < 1:
        raise ConfigurationError("EXTRACTION_BATCH_SIZE debe ser mayor que cero")
    if task_count != 1:
        raise ConfigurationError("Este extractor requiere una sola tarea de Cloud Run")

    credentials, default_project = google.auth.default()
    project_id = config.get("GOOGLE_CLOUD_PROJECT") or default_project
    if not project_id:
        raise ConfigurationError("Configura GOOGLE_CLOUD_PROJECT")

    prefix = config.get("GCS_PREFIX", "raw/mysql").strip("/")
    started = datetime.now(timezone.utc)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{uuid4().hex}"
    run_prefix = "/".join(filter(None, [prefix, f"date={started:%Y-%m-%d}", run_id]))
    log_event("extraction_started", run_id=run_id, bucket=bucket_name,
              prefix=run_prefix)

    with secretmanager.SecretManagerServiceClient(credentials=credentials) as secrets:
        with storage.Client(project=project_id, credentials=credentials) as gcs:
            with conectar_mysql(secrets, project_id, config["secrets"]) as connection:
                extraer_datos_mysql(connection, gcs.bucket(bucket_name),
                                   run_prefix, batch_size)
    log_event("extraction_completed", uri=f"gs://{bucket_name}/{run_prefix}")


def main() -> int:
    try:
        ejecutar_extraccion()
    except ConfigurationError as error:
        log_event("configuration_failed", "ERROR", message=str(error))
        return 1
    except Exception as error:
        # No enviar credenciales ni valores de filas a Cloud Logging.
        log_event("extraction_failed", "ERROR", error_type=type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
