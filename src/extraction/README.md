# Extracción de MariaDB a GCS

Primer contenedor del proyecto. Parte de `extraer_datos_mysql()` de
`../glamour-legacy-dataops/etl_script.py`: conserva la extracción completa de
`persona`, `contenido`, `campana`, `documento` y `documentodetalle`, y los cinco
secretos `MYSQL_*` existentes. El destino de este contenedor es exclusivamente GCS.

Lee cada tabla por lotes, escribe Parquet con compresión Snappy y sube cada parte
antes de continuar. No aplica las funciones de limpieza o modelado del legacy.
El tamaño del lote limita las filas en memoria; también hay que considerar el
tamaño de las filas y del Parquet temporal al dimensionar Cloud Run.

## Configuración

Editar [`config_dev.json`](../../config_dev.json) en la raíz del proyecto. El script
lo carga automáticamente desde esa ubicación, independientemente de la carpeta
desde la que se ejecute. Completar `GCS_BUCKET` y revisar el proyecto.

| Variable | Uso |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | Proyecto que contiene los secretos. Si se omite, usa el proyecto de las credenciales ADC. |
| `GCS_BUCKET` | Bucket existente de la Landing Zone, sin `gs://`. Obligatorio. |
| `GCS_PREFIX` | Prefijo de salida. Por defecto, `raw/mysql`. |
| `EXTRACTION_BATCH_SIZE` | Filas por lote. Por defecto, `50000`. |

La sección `secrets` contiene los **nombres de los secretos** de conexión. Por
ejemplo, `"MYSQL_PASSWORD": "MYSQL_PASSWORD_DEV"` indica que la contraseña debe
leerse del secreto `MYSQL_PASSWORD_DEV` del proyecto configurado. Se consulta la
versión `latest`. Los valores de las credenciales siguen en Secret Manager.

Las variables de entorno de la tabla tienen prioridad sobre el JSON. Si el
archivo no existe, se usan las variables de entorno y los nombres `MYSQL_HOST`,
`MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` y `MYSQL_PORT` del legacy.

## Ejecución local

Desde la raíz del repositorio, con Python 3.11 o superior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/extraction/requirements.txt
gcloud auth application-default login

# Después de completar config_dev.json:
.venv/bin/python src/extraction/extract.py
```

Este comando lee las cinco tablas reales y escribe archivos en el bucket indicado.
La IP del equipo debe estar autorizada para conectarse a MariaDB.

Pruebas sin conexiones a MariaDB ni GCP:

```bash
.venv/bin/python -B -m unittest discover -s src/extraction -v
```

## Contenedor y Cloud Run Job

```bash
docker build --platform linux/amd64 -t glamour-extraction src/extraction/
```

Ejecutar el build desde la raíz del repositorio. `src/extraction/` contiene todo lo
necesario para construir la imagen.

Configurar el Job con una tarea (`--tasks=1`) y las variables anteriores.
`config_dev.json` es para desarrollo local y no se incluye en la imagen.
La cuenta de servicio necesita acceso a las cinco versiones de secretos y permiso
para crear objetos en el bucket. El usuario de MariaDB necesita acceso de lectura
a las cinco tablas. La conectividad conserva el requisito del legacy: salida por
VPC y Cloud NAT con IP fija autorizada por el proveedor.

El proceso termina con código `0` al completar todo y `1` ante un fallo, conforme
al [contrato de Cloud Run Jobs](https://docs.cloud.google.com/run/docs/container-contract).
Emite logs JSON con tabla, parte y cantidad de filas, sin valores de los datos.
Este directorio no crea recursos de infraestructura ni programa ejecuciones.

## Archivos generados

```text
gs://<bucket>/raw/mysql/date=2026-10-24/<fecha-UTC>-<uuid>/
  persona/part-00000.parquet
  contenido/part-00000.parquet
  campana/part-00000.parquet
  documento/part-00000.parquet
  documentodetalle/part-00000.parquet
  manifest.json
```

Cada ejecución e intento usa una ruta nueva. Los uploads usan
[`if_generation_match=0`](https://docs.cloud.google.com/storage/docs/uploading-objects)
para impedir sobrescribir objetos existentes. Esto protege las escrituras del
extractor; la retención del bucket se configura por separado.

`manifest.json` contiene las filas y los objetos de cada tabla y se publica al
terminar las cinco. Una ruta sin manifiesto es una extracción incompleta y no
debe consumirse como un conjunto completo. Un reintento vuelve a leer el origen
y genera otra ruta; no elimina ni reanuda los objetos de un intento anterior.

Los tipos provienen de `information_schema`: se conservan decimales, enteros y
columnas con valores nulos. Las tablas vacías producen un Parquet con su esquema.
`TIMESTAMP` se exporta en UTC; `DATETIME` conserva el valor sin zona horaria.
`TIME` se representa como texto para conservar duraciones negativas o mayores a
24 horas. Un tipo SQL no contemplado detiene la ejecución.

Las tablas se leen secuencialmente; no se garantiza una instantánea transaccional
común a las cinco. Esta versión realiza extracción completa, sin filtros ni CDC.

## GitHub Actions

[`ci-extraction.yml`](../../.github/workflows/ci-extraction.yml) ejecuta las pruebas
con Python 3.11 en cada push, pull request o ejecución manual. Las pruebas usan
dobles de prueba para MariaDB y GCP; no necesitan credenciales.
