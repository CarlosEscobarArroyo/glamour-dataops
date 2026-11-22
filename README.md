# Glamour Perú — Plataforma DataOps Comercial

Monorepo central para la ingesta, validación, modelado dimensional, orquestación y gobierno del ciclo de vida de los datos comerciales de **Glamour Perú** sobre **Google Cloud Platform (GCP)**.

---

## 1. Objetivo del Proyecto

Automatizar y gobernar el flujo de datos comerciales desde la base de datos transaccional (**MariaDB**) hasta los paneles analíticos en **Looker Studio**, aplicando prácticas **DataOps**:

* **Infraestructura como Código (IaC) y CI/CD:** Despliegue reproducible con Terraform y GitHub Actions.
* **Almacenamiento desacoplado e inmutable:** Respaldo histórico en formato Parquet sobre Cloud Storage (*Landing Zone*) y capas analíticas en BigQuery (*Staging* y *Modelo Dimensional*).
* **Control de calidad automatizado:** Validación de datos mediante *suites* de **Great Expectations** antes de permitir la publicación de indicadores.
* **Orquestación serverless:** Ejecución programada, control de errores y detención ante fallos mediante **Cloud Workflows** y **Cloud Run Jobs**.
* **Gobierno y Observabilidad:** Linaje y diccionario de datos en **OpenMetadata**, con monitoreo y alertas centralizadas en **Cloud Logging**, **Cloud Monitoring** y **Datadog**.

---

## 2. Arquitectura del Flujo Operativo

![Arquitectura DataOps Glamour Perú](./docs/Arquitectura.drawio.svg)


1. **Cloud Scheduler (05:00 AM):** Dispara automáticamente el inicio del flujo diario sin intervención manual.
2. **Cloud Workflows (Orquestador Principal):** Coordina la secuencia de pasos, reintentos y manejo de excepciones:
   * **Paso 1 — Cloud Run Job: Extractor (Python + Cloud NAT IP Fija):**
     * Extrae datos desde MariaDB utilizando una IP estática autorizada.
     * Guarda respaldo inmutable (`.parquet`) en Cloud Storage (*Landing Zone*).
   * **Carga a Staging (load jobs de BigQuery, lanzados por el propio Workflow):**
     * Carga los `.parquet` de esa extracción como tablas crudas en el primer dataset de BigQuery (*Capa Staging*).
   * **Paso 2 — BigQuery Stored Procedures / SQL:**
     * Construye el modelo candidato desde *Staging* en `bq_validation`, sin modificar todavía el modelo publicado.
   * **Paso 3 — Cloud Run Job: Data Quality (Great Expectations):**
     * Evalúa completitud, unicidad, integridad referencial y rangos válidos sobre el modelo candidato.
     * Si alguna validación falla, **Cloud Workflows detiene el pipeline** y conserva la última versión publicada.
     * El Job ya está implementado; su llamada desde Workflows se activa después de calibrarlo en dev.
   * **Publicación controlada:**
     * Únicamente si las pruebas de calidad son exitosas, copia `bq_validation` al modelo dimensional que consume Looker Studio.
3. **Looker Studio:** Consulta exclusivamente las tablas validadas del *Modelo Dimensional* para la gerencia y las coordinadoras.

---

## 3. Estructura del Monorepo

Cada contenedor agrupa su código y dependencias en una carpeta dentro de `src/`.
Sus pruebas viven en `tests/`, que replica la estructura de `src/`.

Guía del primer contenedor: [extracción de MariaDB a GCS](./src/extraction/README.md).
Convención de publicación: [imágenes de los Jobs en Artifact Registry](./docs/artifact_registry.md).
El workflow [Deploy Jobs](./.github/workflows/deploy-jobs.yml) ejecuta las pruebas del componente
que cambió, sin acceder a MariaDB ni GCP, y en `dev` y `main` publica su imagen y
despliega su Job. El workflow [Orquestación](./.github/workflows/orchestration.yml)
publica la definición del flujo de Cloud Workflows cuando cambia `src/orchestration/`.
El Job de calidad ya está implementado y se despliega con el mismo CI; todavía
debe calibrarse en dev antes de conectarlo al flujo diario. Gobierno aún no está
implementado.

* **`.github/workflows/`** — Pipelines CI/CD (GitHub Actions)
  * `deploy-jobs.yml`: Workflow único de los Cloud Run Jobs: pruebas, imagen y despliegue del componente que cambió.
  * `orchestration.yml`: Valida y publica la definición del workflow de Cloud Workflows.
  * `transformation.yml`: Publica el SQL de `src/transformation/` como procedimientos de BigQuery y carga `ref_ubigeo.csv`.
  * `terraform.yml`: Validación, plan y despliegue de la infraestructura en GCP (`dev` / `prod`).
* **`infra/`** — Infraestructura como Código (Terraform)
  * `modules/`: Módulos reutilizables (`storage`, `bigquery`, `cloud_run`, `iam`, `vpc`).
  * `environments/dev/`: Configuración del entorno `glamour-dataops-dev`.
  * `environments/prod/`: Configuración del entorno `glamour-dataops-prod`.
* **`src/`** — Código fuente del pipeline
  * [`extraction/`](./src/extraction/README.md): Contenedor 1 — Cloud Run Job de extracción en Python. MariaDB → Parquet en GCS.
  * [`quality/`](./src/quality/README.md): Contenedor 2 — Cloud Run Job de calidad con Great Expectations. Tiene contratos para las once tablas y reglas profundas para el piloto; falta activarlo en la orquestación.
  * `transformation/`: Modelo dimensional en SQL. Un archivo por tabla (dimensiones y hechos) y `ref_ubigeo.csv`, la tabla de referencia de ubicaciones.
  * `orchestration/`: Definición del orquestador. `workflow_comercial.yaml` es el flujo de Google Cloud Workflows: extracción, carga a Staging, construcción del modelo dimensional y su publicación. La llamada al Job de calidad está pendiente hasta calibrarlo en dev.
* **`tests/`** — Pruebas, con la misma estructura que `src/`
  * `extraction/`: Pruebas unitarias del extractor.
  * `quality/`: Pruebas unitarias de configuración, contratos, resultados y publicación de Data Docs, sin acceder a GCP.
  * `transformation/`: Pruebas de los archivos SQL y de `ref_ubigeo.csv`, sin acceder a BigQuery.
* **`governance/`** — Documentación base y configuración de OpenMetadata
  * `data_dictionary.md`: Diccionario de datos de tablas y columnas.
  * `metrics_glossary.md`: Definición oficial de indicadores comerciales (ej. Ventas).
  * `openmetadata/`: Conectores e ingesta de metadatos y linaje.
* **`README.md`** — Documentación general del repositorio.

---

## 4. Stack Tecnológico

| Categoría | Tecnologías |
| :--- | :--- |
| **Colaboración, CI/CD e IaC** | GitHub, GitHub Actions, Docker, Terraform |
| **Orquestación** | Google Cloud Workflows, Cloud Scheduler |
| **Cómputo Serverless** | Google Cloud Run Jobs, Artifact Registry |
| **Almacenamiento y Transformación** | Google Cloud Storage (Parquet), BigQuery, SQL, Python |
| **Calidad de Datos** | Great Expectations |
| **Gobierno y Metadatos** | OpenMetadata, BigQuery Policy Tags (Data Masking) |
| **Observabilidad y Alertas** | Cloud Logging, Cloud Monitoring, Datadog |
| **Consumo Analítico** | Looker Studio |

---

## 5. Configuración del Entorno Local

### Prerrequisitos
* **Python 3.11+** (gestión recomendada con `uv` o `venv`)
* **Docker**
* **Terraform >= 1.6**
* **Google Cloud SDK (`gcloud`)**

### Autenticación en GCP
1. Iniciar sesión en Google Cloud CLI:
   `gcloud auth login`
2. Configurar credenciales por defecto para aplicaciones locales y Terraform:
   `gcloud auth application-default login`
3. Definir el proyecto activo de desarrollo:
   `gcloud config set project glamour-dataops-dev`

Para correr las pruebas del extractor, consultar la
[guía de extracción](./src/extraction/README.md). El extractor no se ejecuta en
local: se valida con sus pruebas y ejecutando el Job en dev.

---

## 6. Gestión de la Configuración

Diseño acordado para variables de entorno, secretos y valores por ambiente.
Describe el estado objetivo; su implementación está pendiente.

**Principio:** cada valor vive en un solo lugar, y ese lugar depende del tipo de
valor. El código de los componentes solo lee variables de entorno.

### Dónde vive cada tipo de valor

| Tipo | Ejemplos | Dónde vive |
| :--- | :--- | :--- |
| Identidad del ambiente | Proyecto, región | Variables de GitHub por ambiente (para el CI) y `terraform.tfvars` (para la plataforma) |
| Referencias a recursos | Bucket landing, cuenta de servicio, red | `job.yaml`, formadas a partir del proyecto (`${PROJECT_ID}-cs-landing`) |
| Secretos | `MYSQL_HOST`, `MYSQL_PASSWORD` | Valor en Secret Manager; referencia en `job.yaml`; Cloud Run los inyecta como variables de entorno |
| Datos de conexión no secretos | Puerto, base y usuario de MariaDB | `job.yaml`, escritos directamente: son iguales en dev y prod |
| Políticas del ambiente | Retención, scheduler pausado, protección contra borrado | `terraform.tfvars` |
| Dimensionamiento del Job | CPU, memoria, timeout, reintentos | `job.yaml` |
| Parámetros de operación | Tamaño de lote, timeouts de conexión | Constante en el código; pasa a variable en `job.yaml` solo si un ambiente necesita otro valor |
| Reglas del pipeline | Lista de tablas, formato, rutas, expectativas, SQL | Código |
| Identidad de despliegue | Proveedor y cuenta para autenticar GitHub contra GCP | Variables de GitHub por ambiente |

### Quién es dueño de qué

* **Terraform:** la plataforma. Proyecto, red, cuentas de servicio y permisos, buckets, datasets, secretos vacíos, Artifact Registry, y el workflow (su cuenta y sus variables, no su contenido) y el scheduler.
* **CI de transformación:** el modelo dimensional. Guarda cada `.sql` de `src/transformation/` como procedimiento almacenado en `bq_validation` y carga `ref_ubigeo.csv` en `bq_staging`.
* **CI de orquestación:** el contenido del workflow. Publica `src/orchestration/workflow_comercial.yaml` con `gcloud workflows deploy` cuando cambia.
* **CI de los Jobs:** cada Cloud Run Job completo. Un único workflow detecta qué componente de `src/` cambió y, para ese componente, ejecuta las pruebas, construye y publica la imagen, rellena los marcadores de `job.yaml` y lo aplica con `gcloud run jobs replace`. Falla si queda un marcador sin resolver.
* **Ramas:** `dev` despliega al proyecto dev; `main` despliega a prod con aprobación.

### Archivos de un componente

Cada componente tiene en `src/<componente>/` su código, su `Dockerfile` y un
`job.yaml` que define el Job: imagen, variables de entorno, referencias a secretos,
recursos, cuenta de servicio y red. El mismo archivo sirve para dev y prod; solo
cambian los marcadores. Las pruebas viven en `tests/<componente>/`, en una carpeta
`tests/` de la raíz que replica la estructura de `src/`.

Para el extractor:

| Lugar | Contenido |
| :--- | :--- |
| `src/extraction/extract.py` | Lee `GCS_BUCKET` y las cinco `MYSQL_*`. Nombra en el log las que falten y la causa de un fallo de conexión |
| `src/extraction/job.yaml` | Imagen, las seis variables del contenedor (cuatro con valor y dos secretos), recursos, cuenta de servicio y red |
| `tests/extraction/` | Pruebas unitarias |
| `.github/workflows/deploy-jobs.yml` | Pruebas, imagen y despliegue |
| Secret Manager de cada proyecto | Valores de `MYSQL_HOST` y `MYSQL_PASSWORD` |

`config_dev.json` desaparece. La ejecución local queda fuera de alcance: el
extractor se valida con las pruebas unitarias y ejecutando el Job en dev.

### Variables de GitHub

Cuatro por ambiente (`dev` y `prod`), compartidas por todos los componentes:
`PROJECT_ID`, `REGION`, `WIF_PROVIDER` (proveedor de identidad) y `DEPLOY_SA`
(cuenta de despliegue).
Solo se agrega otra cuando un valor difiere entre ambientes y no puede formarse
a partir del proyecto.

### Qué tocar según el cambio

| Cambio | Dónde |
| :--- | :--- |
| Lógica o valor por defecto | Código |
| Memoria, timeout, una variable distinta por ambiente | `job.yaml` |
| Contraseña u otro secreto | Secret Manager, sin desplegar |
| Pasos del pipeline | `src/orchestration/workflow_comercial.yaml` |
| Lógica de una dimensión o tabla de hechos | Su archivo en `src/transformation/` |
| Ubicación de un distrito | `src/transformation/ref_ubigeo.csv` |
| Recurso o permiso nuevo, política del ambiente | Terraform |

### Pendiente de decidir

Imagen de prod: reconstruirla al hacer merge a `main` o copiar la validada en dev.

---

## 7. Roles y Seguridad de Accesos (IAM)

* **Responsable de Negocio:** Definición y validación de reglas de indicadores comerciales y criterios de aceptación.
* **Responsable de Ingeniería de Datos:** Mantenimiento del pipeline ELT (Python/SQL), integración entre MariaDB, Cloud Storage y BigQuery, e infraestructura en Terraform.
* **Responsable de Calidad de Datos:** Definición y supervisión de *suites* de validación en Great Expectations.
* **Operación de Plataforma:** Supervisión de ejecuciones en Cloud Scheduler/Workflows y atención de alertas en Cloud Monitoring y Datadog.
* **Consumidores Analíticos:** Gerencia y coordinadoras mediante paneles en Looker Studio.
* **Protección de Datos Sensibles (PII):** Cero credenciales en código (uso de **Google Secret Manager**). Los archivos crudos en Cloud Storage están restringidos a las cuentas de servicio del pipeline y las columnas sensibles en BigQuery cuentan con **Policy Tags y Enmascaramiento Dinámico (SHA-256)**.

ROLES IAM ASIGNADOS AL EQUIPO DATAOPS (NIVEL PROYECTO)

1. Browser (roles/browser)
   - Navegación general en la consola de Google Cloud sin acceso a datos.

2. BigQuery Data Viewer (roles/bigquery.dataViewer)
   - Lectura de tablas y vistas en BigQuery (sujeto a reglas de enmascaramiento / Policy Tags).

3. BigQuery Job User (roles/bigquery.jobUser)
   - Permiso para ejecutar consultas SQL (jobs) dentro del proyecto.

4. Cloud Run Developer (roles/run.developer)
   - Visualización, despliegue y ejecución de los contenedores de Cloud Run Jobs (Extracción y Calidad).

5. Workflows Admin (roles/workflows.admin)
   - Gestión y ejecución de los flujos de orquestación en Cloud Workflows.

6. Secret Manager Viewer (roles/secretmanager.viewer)
   - Visualización de la existencia y metadatos de secretos, sin acceso a leer el valor/contraseña.

7. Logs Viewer (roles/logging.viewer)
   - Lectura de registros de ejecución y trazas de error en Cloud Logging.


ROL IAM ADICIONAL (NIVEL BUCKET DE CLOUD STORAGE)

8. Storage Legacy Bucket Reader (roles/storage.legacyBucketReader)
   - Permite ver el bucket y listar los archivos .parquet en la Landing Zone, sin permiso para descargarlos ni abrir su contenido.
