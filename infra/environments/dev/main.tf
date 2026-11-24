# Plataforma DataOps de Glamour Perú. Este archivo es igual en dev y prod:
# lo que cambia entre entornos está en terraform.tfvars y backend.tf.

locals {
  prefijo = var.project_id # convención: <proyecto>-<tipo>-<propósito>
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
}

module "vpc" {
  source  = "../../modules/vpc"
  prefijo = local.prefijo
  region  = var.region
}

module "secrets" {
  source  = "../../modules/secrets"
  nombres = ["MYSQL_HOST", "MYSQL_PASSWORD"] # el resto de la conexión va en job.yaml
  lectores = {
    extraction = module.iam.members.extraction
  }
}

module "storage" {
  source         = "../../modules/storage"
  project_id     = var.project_id
  region         = var.region
  retencion_dias = var.retencion_dias

  landing_escritores   = { extraction = module.iam.members.extraction }
  landing_lectores     = { workflows = module.iam.members.workflows } # carga de la landing a staging
  data_docs_escritores = { calidad = module.iam.members.quality }
}

module "bigquery" {
  source   = "../../modules/bigquery"
  location = var.bq_location

  # sa-deploy carga la tabla de referencia ref_ubigeo y publica los procedimientos.
  staging_editores     = { workflows = module.iam.members.workflows, deploy = module.iam.members.deploy }
  staging_lectores     = { calidad = module.iam.members.quality }
  validation_editores  = { workflows = module.iam.members.workflows, deploy = module.iam.members.deploy }
  validation_lectores  = { calidad = module.iam.members.quality }
  dimensional_editores = { workflows = module.iam.members.workflows }
  dimensional_lectores = { looker = module.iam.members.looker }
}

# Datos personales de las vendedoras: solo los dueños del proyecto (roles/owner)
# ven el valor real. Si cambia quién es dueño, hay que volver a aplicar.
data "google_project_iam_policy" "actual" {
  project = var.project_id
}

locals {
  duenos = toset(flatten([
    for b in jsondecode(data.google_project_iam_policy.actual.policy_data).bindings :
    [for m in b.members : m if startswith(m, "user:") || startswith(m, "group:")]
    if b.role == "roles/owner"
  ]))
}

module "gobierno" {
  source   = "../../modules/gobierno"
  prefijo  = local.prefijo
  location = lower(var.bq_location)

  # sa-workflows lee el valor real para construir y publicar dim_vendedor.
  lectores_reales = merge(
    { for m in local.duenos : m => m },
    { workflows = module.iam.members.workflows },
  )

  lectores_enmascarados = {
    looker  = module.iam.members.looker
    calidad = module.iam.members.quality
  }

  etiquetadores = { workflows = module.iam.members.workflows }

  datasets = [
    module.bigquery.staging_dataset,
    module.bigquery.validation_dataset,
    module.bigquery.dimensional_dataset,
  ]
}

# Convención de docs/artifact_registry.md: un repositorio por proyecto, una imagen por
# componente (extraction, quality) y etiquetas inmutables. Sin borrado automático.
resource "google_artifact_registry_repository" "imagenes" {
  repository_id = "${var.project_id}-ar-jobs"
  location      = var.region
  format        = "DOCKER"
  description   = "Imágenes de los Cloud Run Jobs (extracción y calidad)."

  docker_config {
    immutable_tags = true
  }
}

# Los Cloud Run Jobs no se crean aquí: los despliega el CI (.github/workflows/deploy-jobs.yml)
# desde src/<componente>/job.yaml. Terraform solo le da a sa-deploy lo que necesita.
resource "google_artifact_registry_repository_iam_member" "deploy" {
  repository = google_artifact_registry_repository.imagenes.name
  location   = google_artifact_registry_repository.imagenes.location
  role       = "roles/artifactregistry.writer"
  member     = module.iam.members.deploy
}

module "orchestration" {
  source              = "../../modules/orchestration"
  nombre              = "${local.prefijo}-wf-pipeline"
  region              = var.region
  workflows_sa        = module.iam.emails.workflows
  scheduler_sa        = module.iam.emails.scheduler
  pausado             = var.scheduler_pausado
  deletion_protection = var.proteger

  variables = {
    # Nombres que el CI da a los Jobs (metadata.name de cada job.yaml).
    JOB_EXTRACCION     = "${local.prefijo}-crj-extraction"
    JOB_CALIDAD        = "${local.prefijo}-crj-quality"
    LANDING_BUCKET     = module.storage.landing_bucket
    DATASET_STAGING    = module.bigquery.staging_dataset
    DATASET_VALIDATION = module.bigquery.validation_dataset
    DATASET_DIMENSION  = module.bigquery.dimensional_dataset
    # Etiqueta que el workflow pone en las columnas con datos personales.
    POLICY_TAG_DATO_PERSONAL = module.gobierno.policy_tag
  }
}

# Catálogo de datos. Solo existe donde openmetadata = true (ver terraform.tfvars).
module "openmetadata" {
  count              = var.openmetadata ? 1 : 0
  source             = "../../modules/openmetadata"
  prefijo            = local.prefijo
  ambiente           = module.iam.ambiente
  region             = var.region
  zona               = "${var.region}-b"
  network_id         = module.vpc.network_id
  subnet_id          = module.vpc.subnet_id
  acceso_web_publico = true
}

# API key de Datadog para monitorear OpenMetadata. Va en su propio módulo para que
# solo la VM pueda leerla (el módulo da acceso a todos los secretos de la lista).
module "secrets_datadog" {
  count   = var.openmetadata ? 1 : 0
  source  = "../../modules/secrets"
  nombres = ["datadog-openmetadata-dev-api-key"]
  lectores = {
    openmetadata = module.openmetadata[0].member
  }
}

# El secreto se creó a mano con gcloud; este bloque lo adopta sin recrearlo.
import {
  to = module.secrets_datadog[0].google_secret_manager_secret.secreto["datadog-openmetadata-dev-api-key"]
  id = "projects/${var.project_id}/secrets/datadog-openmetadata-dev-api-key"
}
