# Plataforma DataOps de Glamour Perú. Este archivo es igual en dev y prod:
# lo que cambia entre entornos está en terraform.tfvars y backend.tf.

locals {
  prefijo        = "glamour"
  ruta_workflow  = "${path.root}/../../../orchestration/workflow_comercial.yaml"
  secretos_mysql = ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "MYSQL_PORT"]
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  equipo     = var.equipo
}

module "vpc" {
  source  = "../../modules/vpc"
  prefijo = local.prefijo
  region  = var.region
}

module "secrets" {
  source  = "../../modules/secrets"
  nombres = local.secretos_mysql
  lectores = {
    extractor = module.iam.members.extractor
  }
}

module "storage" {
  source         = "../../modules/storage"
  project_id     = var.project_id
  region         = var.region
  retencion_dias = var.retencion_dias

  landing_escritores   = { extractor = module.iam.members.extractor }
  landing_lectores     = { workflows = module.iam.members.workflows } # carga de la landing a staging
  landing_listadores   = module.iam.equipo_members
  data_docs_escritores = { calidad = module.iam.members.calidad }
}

module "bigquery" {
  source   = "../../modules/bigquery"
  location = var.bq_location

  staging_editores     = { workflows = module.iam.members.workflows }
  staging_lectores     = { calidad = module.iam.members.calidad }
  dimensional_editores = { workflows = module.iam.members.workflows }
  dimensional_lectores = { looker = module.iam.members.looker }
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

module "job_extraccion" {
  source              = "../../modules/cloud_run_job"
  nombre              = "${local.prefijo}-extraccion"
  region              = var.region
  service_account     = module.iam.emails.extractor
  network_id          = module.vpc.network_id
  subnet_id           = module.vpc.subnet_id
  memoria             = "4Gi"
  deletion_protection = var.proteger
  ejecutores          = { workflows = module.iam.members.workflows }

  # Las mismas variables que lee src/extraction/extract.py.
  env = {
    GOOGLE_CLOUD_PROJECT  = var.project_id
    GCS_BUCKET            = module.storage.landing_bucket
    EXTRACTION_BATCH_SIZE = "50000"
  }
}

module "job_calidad" {
  source              = "../../modules/cloud_run_job"
  nombre              = "${local.prefijo}-calidad"
  region              = var.region
  service_account     = module.iam.emails.calidad
  deletion_protection = var.proteger
  ejecutores          = { workflows = module.iam.members.workflows }

  env = {
    GOOGLE_CLOUD_PROJECT = var.project_id
    BQ_DATASET           = module.bigquery.staging_dataset
    DATA_DOCS_BUCKET     = module.storage.data_docs_bucket
  }
}

module "orchestration" {
  source              = "../../modules/orchestration"
  nombre              = "${local.prefijo}-pipeline"
  region              = var.region
  workflows_sa        = module.iam.emails.workflows
  scheduler_sa        = module.iam.emails.scheduler
  definicion          = fileexists(local.ruta_workflow) ? file(local.ruta_workflow) : null
  pausado             = var.scheduler_pausado
  deletion_protection = var.proteger

  variables = {
    JOB_EXTRACCION    = module.job_extraccion.nombre
    JOB_CALIDAD       = module.job_calidad.nombre
    LANDING_BUCKET    = module.storage.landing_bucket
    DATASET_STAGING   = module.bigquery.staging_dataset
    DATASET_DIMENSION = module.bigquery.dimensional_dataset
  }
}
