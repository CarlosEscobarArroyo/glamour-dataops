"""Extrae las 18 tablas comerciales seleccionadas y guarda sus datos crudos en GCS."""

from datetime import datetime, timedelta, timezone
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


# Las pone el Job (src/extraction/job.yaml); MYSQL_HOST y MYSQL_PASSWORD llegan
# desde Secret Manager.
ENV_VARS = (
    "GCS_BUCKET", "MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD",
    "MYSQL_DATABASE", "MYSQL_PORT",
)

BATCH_SIZE = 50000  # filas por lote; limita la memoria usada por tabla

# Las carpetas y horas de cada ejecución usan hora de Perú (UTC-5, sin horario
# de verano).
HORA_PERU = timezone(timedelta(hours=-5))

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
# Fechas y horas se guardan como texto: la base tiene valores inválidos
# ("0000-00-00", TIME de más de 24 horas). Se convierten en la capa analítica.
TEMPORALES = {"date", "datetime", "timestamp", "time"}


def log_event(event: str, severity: str = "INFO", **fields) -> None:
    """Escribe un evento en el log como una línea JSON.

    Cloud Logging lee ese JSON y lo muestra con su severidad y sus campos, lo
    que permite filtrar por evento, tabla, etc.
    """
    print(json.dumps({"severity": severity, "event": event, **fields}), flush=True)


def conectar_mysql() -> pymysql.connections.Connection:
    """Abre y devuelve la conexión a MySQL.

    Toma el servidor, el usuario, la contraseña, la base y el puerto de las
    variables de entorno MYSQL_*. Si la conexión falla, registra el error en
    el log y lo vuelve a lanzar.
    """
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
    """Devuelve el nombre de una tabla o columna entre comillas invertidas.

    Así el nombre puede usarse en una consulta aunque sea una palabra
    reservada de SQL o contenga caracteres especiales: order -> `order`.
    """
    return "`" + identifier.replace("`", "``") + "`"


def arrow_type(data_type: str, column_type: str, precision, scale) -> pa.DataType:
    """Devuelve el objeto de PyArrow que describe el tipo de una columna MySQL.

    El tipo se toma del esquema de la tabla y no de los datos, para que sea
    siempre el mismo aunque un lote venga vacío o con solo valores NULL.
    Así todos los archivos de una tabla comparten esquema y no fallan al
    cargarse juntos.

    Las fechas y horas se devuelven como texto. Si el tipo SQL no está
    contemplado, lanza ValueError.
    """
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


def esquema_tabla(connection, table: str) -> tuple[pa.Schema, str]:
    """Devuelve el esquema PyArrow de una tabla MySQL y las columnas para su SELECT.

    Consulta en MySQL la definición de la tabla (nombre, tipo y si admite NULL
    de cada columna) y devuelve dos cosas:

    - El esquema PyArrow con el que se escriben los datos de la tabla.
    - El texto con la lista de columnas para armar el SELECT de extracción.
      Las fechas y horas se piden convertidas a texto (CAST ... AS CHAR).

    Lanza ValueError si la tabla no existe o tiene una columna de un tipo no
    soportado.
    """
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


def extraer_tabla(connection, bucket, table: str, run_prefix: str, batch_size: int) -> dict:
    """Copia una tabla MySQL completa al bucket como archivos Parquet.

    Lee la tabla por lotes de batch_size filas, para no cargarla entera en
    memoria, y sube cada lote como un archivo aparte:
    {run_prefix}/{table}/part-00000.parquet, part-00001.parquet, ...

    Si la tabla está vacía sube igualmente un Parquet sin filas, para que su
    esquema quede publicado. No sobrescribe: si un archivo ya existe en el
    bucket, la subida falla.

    Devuelve un diccionario con el total de filas ("rows") y los nombres de
    los archivos subidos ("objects").
    """
    schema, expressions = esquema_tabla(connection, table)
    objects = []
    total_rows = 0
    with TemporaryDirectory(prefix="glamour-extraction-") as directory:
        path = Path(directory) / "part.parquet"
        # Un cursor sin buffer evita traer toda la tabla a memoria.
        with connection.cursor(pymysql.cursors.SSCursor) as cursor:
            cursor.execute(f"SELECT {expressions} FROM {quoted(table)}")
            rows = cursor.fetchmany(batch_size)
            # "or not objects" hace que una tabla vacía suba igual un Parquet
            # sin filas, para que su esquema quede publicado.
            while rows or not objects:
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
                rows = cursor.fetchmany(batch_size)

    return {"rows": total_rows, "objects": objects}


def extraer_datos_mysql(connection, bucket, run_prefix: str, batch_size: int) -> dict:
    """Copia al bucket todas las tablas de TABLAS y publica el manifiesto.

    Extrae las tablas una por una con extraer_tabla. Al terminar todas, sube
    {run_prefix}/manifest.json con el resumen de la ejecución: las filas y los
    archivos de cada tabla. Si alguna tabla falla no se sube el manifiesto,
    así que su presencia indica que la extracción está completa.

    Devuelve el contenido del manifiesto.
    """
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
        "completed_at": datetime.now(HORA_PERU).isoformat(),
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
    """Ejecuta una extracción completa de MySQL al bucket.

    La carpeta de destino es la que indique la variable de entorno RUN_PREFIX,
    que pone el workflow para saber luego dónde leer. Si no viene (ejecución
    manual del Job), se genera una con fecha y hora de Perú y un identificador
    único: date=AAAA-MM-DD/{run_id}.

    Luego abre el cliente de Cloud Storage y la conexión a MySQL, extrae todas
    las tablas y cierra ambos al terminar.
    """
    bucket = os.environ["GCS_BUCKET"]
    run_prefix = os.environ.get("RUN_PREFIX")
    if not run_prefix:
        started = datetime.now(HORA_PERU)
        run_id = f"{started:%Y%m%dT%H%M%S}-{uuid4().hex}"
        run_prefix = f"date={started:%Y-%m-%d}/{run_id}"
    log_event("extraction_started", bucket=bucket, prefix=run_prefix)

    with storage.Client() as gcs, conectar_mysql() as connection:
        extraer_datos_mysql(connection, gcs.bucket(bucket), run_prefix, BATCH_SIZE)
    log_event("extraction_completed", uri=f"gs://{bucket}/{run_prefix}")


def main() -> int:
    """Punto de entrada del Job: valida el entorno y ejecuta la extracción.

    Devuelve el código de salida del proceso: 0 si todo salió bien y 1 si
    falta alguna variable de entorno o la extracción falló. Los errores se
    registran en el log sin su mensaje, para no exponer credenciales ni datos.
    """
    missing_env_vars = [name for name in ENV_VARS if not os.environ.get(name)]
    if missing_env_vars:
        log_event("extraction_failed", "ERROR",
                  message=f"Faltan variables de entorno: {', '.join(missing_env_vars)}")
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
