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
     * Carga tablas crudas en el primer dataset de BigQuery (*Capa Staging*).
   * **Paso 2 — Cloud Run Job: Data Quality (Great Expectations):**
     * Evalúa reglas de completitud, unicidad, integridad referencial y rangos válidos sobre la *Capa Staging*.
     * Si alguna validación falla, **Cloud Workflows detiene el pipeline** y envía alerta inmediata hacia **Datadog**.
   * **Paso 3 — BigQuery Stored Procedures / SQL:**
     * Únicamente si las pruebas de calidad son exitosas, transforma y consolida los datos desde *Staging* hacia el segundo dataset de BigQuery (*Modelo Dimensional*).
3. **Looker Studio:** Consulta exclusivamente las tablas validadas del *Modelo Dimensional* para la gerencia y las coordinadoras.

---

## 3. Estructura del Monorepo

Cada contenedor agrupa su código, dependencias y pruebas en una carpeta dentro de `src/`.

Guía del primer contenedor: [extracción de MariaDB a GCS](./src/extraction/README.md).
El workflow [CI extracción](./.github/workflows/ci-extraction.yml) ejecuta las pruebas
con Python 3.11 en cada push, pull request o ejecución manual, sin acceder a MariaDB ni GCP.
Los componentes siguientes describen la estructura objetivo; las carpetas de
calidad, transformación, infraestructura y orquestación aún no están implementadas.

* **`.github/workflows/`** — Pipelines CI/CD (GitHub Actions)
  * `ci-extraction.yml`: Pruebas unitarias del extractor (implementado).
  * `cd-terraform.yml`: Despliegue de infraestructura en GCP (`dev` / `prod`), pendiente.
  * `cd-containers.yml`: Construcción y publicación de imágenes Docker en Artifact Registry, pendiente.
* **`infra/`** — Infraestructura como Código (Terraform)
  * `modules/`: Módulos reutilizables (`storage`, `bigquery`, `cloud_run`, `iam`, `vpc`).
  * `environments/dev/`: Configuración del entorno `glamour-dataops-dev`.
  * `environments/prod/`: Configuración del entorno `glamour-dataops-prod`.
* **`src/`** — Código fuente del pipeline
  * [`extraction/`](./src/extraction/README.md): Contenedor 1 — Cloud Run Job de extracción en Python. MariaDB → Parquet en GCS.
  * `quality/`: Contenedor 2 — Cloud Run Job de calidad con Great Expectations, pendiente.
  * `transformation/`: Consultas y modelado en BigQuery, pendiente.
* **`orchestration/`** — Definición del orquestador
  * `workflow_comercial.yaml`: Flujo declarativo de Google Cloud Workflows.
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

Para configurar `config_dev.json`, ejecutar el extractor o correr las pruebas,
consultar la [guía de extracción](./src/extraction/README.md).

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
