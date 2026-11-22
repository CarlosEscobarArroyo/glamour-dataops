# Extracción de MariaDB a GCS

Primer contenedor del proyecto. Parte de `extraer_datos_mysql()` de
`../glamour-legacy-dataops/etl_script.py`: extrae las 18 tablas comerciales
definidas en `TABLAS` de [`extract.py`](extract.py), dentro de la base seleccionada
por `MYSQL_DATABASE`. El destino es exclusivamente GCS.

| Grupo | Tablas |
| --- | --- |
| Cinco originales | `persona`, `contenido`, `campana`, `documento`, `documentodetalle` |
| Inventario | `stockcontrol`, `stockmovi`, `stocknotas` |
| Configuración de campañas | `contenidoprenda`, `campanarangos` |
| Facturación y saldos | `sventas`, `personasaldos` |
| Catálogos y clasificación | `webparametros`, `webmodulos`, `pagepagos`, `seccion`, `seccioncontenido` |
| Referencias documentales | `documentofile` |

La selección es explícita: no incorpora automáticamente tablas nuevas ni vistas.
Si alguna tabla seleccionada falta o no puede leerse, la ejecución falla y no
publica el manifiesto completo. `senvios`, `personaventas`, `webubigeo`, `webzonas`,
`webzonasdet` y `webcostos` quedan fuera. La referencia geográfica externa del
legacy (`tabla_cruzada.xlsx`) no forma parte de este contenedor.

Lee cada tabla por lotes, escribe Parquet con compresión Snappy y sube cada parte
antes de continuar. No aplica las funciones de limpieza o modelado del legacy.
El tamaño del lote limita las filas en memoria; también hay que considerar el
tamaño de las filas y del Parquet temporal al dimensionar Cloud Run.

## Configuración

El extractor solo lee variables de entorno; no hay archivo de configuración. Las
seis son obligatorias y las define el Job en `job.yaml` (ver la
[gestión de la configuración](../../README.md#6-gestión-de-la-configuración)).

| Variable | Uso | Origen |
| --- | --- | --- |
| `GCS_BUCKET` | Bucket de la Landing Zone, sin `gs://` | Valor en `job.yaml` |
| `MYSQL_HOST` | Host de MariaDB | Secret Manager, inyectada por Cloud Run |
| `MYSQL_PORT` | Puerto de MariaDB | Valor en `job.yaml` |
| `MYSQL_DATABASE` | Base de datos de origen | Valor en `job.yaml` |
| `MYSQL_USER` | Usuario de lectura | Valor en `job.yaml` |
| `MYSQL_PASSWORD` | Contraseña | Secret Manager, inyectada por Cloud Run |
| `RUN_PREFIX` | Carpeta de destino dentro del bucket (opcional) | El workflow, al ejecutar el Job |

Dev y prod leen la misma MariaDB, por lo que los datos de conexión son iguales
en ambos ambientes; el host y la contraseña son secretos. Si falta alguna variable o
está vacía, el proceso termina antes de conectarse y el log las nombra.

El tamaño de lote (`BATCH_SIZE`, 50000 filas), los tiempos de espera de conexión
y la lista de tablas son constantes de [`extract.py`](extract.py).

La ejecución local queda fuera de alcance: el extractor se valida con las pruebas
unitarias y ejecutando el Job en el proyecto dev.

## Pruebas

Viven en [`tests/extraction/`](../../tests/extraction/), en la carpeta `tests/` de
la raíz que replica la estructura de `src/`. No abren conexiones a MariaDB ni a GCP.
Desde la raíz del repositorio, con Python 3.11 o superior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/extraction/requirements.txt
.venv/bin/python -B -m unittest discover -s tests/extraction -v
```

## Contenedor y Cloud Run Job

La imagen se llama `extraction`, dentro del repositorio
`glamour-dataops-dev-ar-jobs`. La región es `us-east1`. Ver la
[estructura y el versionado en Artifact Registry](../../docs/artifact_registry.md)
para publicar imágenes. Para una construcción local:

```bash
docker build --platform linux/amd64 -t extraction:local src/extraction/
```

Ejecutar el build desde la raíz del repositorio. `src/extraction/` contiene todo lo
necesario para construir la imagen.

El Job está definido en [`job.yaml`](job.yaml) y lo despliega el CI. Se ejecuta
con una sola tarea y con las variables de la sección anterior. La cuenta de servicio necesita acceso a los secretos
`MYSQL_HOST` y `MYSQL_PASSWORD` y permiso para crear objetos en el bucket. El usuario de MariaDB
necesita acceso de lectura a las 18 tablas seleccionadas. La conectividad conserva
el requisito del legacy: salida por VPC y Cloud NAT con IP fija autorizada por el
proveedor.

El proceso termina con código `0` al completar todo y `1` ante un fallo, conforme
al [contrato de Cloud Run Jobs](https://docs.cloud.google.com/run/docs/container-contract).
Emite logs JSON con tabla, parte y cantidad de filas, sin valores de los datos.
Un fallo de conexión registra el mensaje de MariaDB, que incluye host y usuario
pero nunca la contraseña. Este directorio no crea recursos de infraestructura ni
programa ejecuciones.

## Archivos generados

```text
gs://<bucket>/date=2026-10-24/<fecha-hora-Perú>-<uuid>/
  persona/part-00000.parquet
  contenido/part-00000.parquet
  campana/part-00000.parquet
  documento/part-00000.parquet
  documentodetalle/part-00000.parquet
  stockcontrol/part-00000.parquet
  ... (las demás tablas seleccionadas)
  manifest.json
```

Cada ejecución usa una ruta nueva: la que envía el workflow en `RUN_PREFIX` o,
si el Job se ejecuta a mano, una generada con la fecha y hora de Perú. Los uploads usan
[`if_generation_match=0`](https://docs.cloud.google.com/storage/docs/uploading-objects)
para impedir sobrescribir objetos existentes. Esto protege las escrituras del
extractor; la retención del bucket se configura por separado.

`manifest.json` contiene `scope: "selected_tables"`, la lista `selected_tables`,
las filas leídas y los archivos de cada tabla en `tables`. Se publica al terminar
las 18 tablas. Una ruta sin manifiesto es una extracción incompleta y no
debe consumirse como un conjunto completo. El Job no reintenta
(`maxRetries: 0`): lo hace el workflow, que vuelve a leer el origen en otra ruta;
no elimina ni reanuda los objetos de un intento anterior.

Los tipos provienen de `information_schema`: se conservan decimales, enteros y
columnas con valores nulos. Las tablas vacías producen un Parquet con su esquema.
`DATE`, `DATETIME`, `TIMESTAMP` y `TIME` se exportan como texto SQL
(`CAST(... AS CHAR)`), sin convertir: así se preservan las fechas cero
(`0000-00-00`) del origen y las duraciones `TIME` negativas o mayores a 24 horas.
El texto de `TIMESTAMP` está en UTC; `DATETIME` conserva el valor sin zona horaria.
La conversión a tipos de fecha y la regla para las fechas cero corresponden a la
capa analítica. Un tipo SQL no contemplado detiene la ejecución.

Las tablas se leen secuencialmente; no se garantiza una instantánea transaccional
común a todas las tablas. Esta versión realiza extracción completa, sin filtros ni CDC.
El esquema de columnas se consulta antes de leer cada tabla; cambios de esquema
durante la ejecución pueden provocar errores. No exporta DDL,
procedimientos ni archivos externos referenciados por columnas.

La selección se basa en la extracción exploratoria y las decisiones posteriores
del proyecto. No aplica filtros de filas ni exclusiones de columnas; cambiar la
selección de tablas no valida automáticamente las reglas de los indicadores.

Las pruebas unitarias no sustituyen la validación contra los datos reales.

## GitHub Actions

[`deploy-jobs.yml`](../../.github/workflows/deploy-jobs.yml) es el workflow único de todos los
Jobs. Cuando cambia `src/extraction/` o `tests/extraction/`, ejecuta las pruebas con
Python 3.11; en `dev` y `main` además publica la imagen y aplica `job.yaml`. Las
pruebas usan dobles de prueba para MariaDB y GCP; no necesitan credenciales.
