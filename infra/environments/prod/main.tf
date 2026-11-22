# Plataforma DataOps de Glamour Perú. Este archivo es igual en dev y prod:
# lo que cambia entre entornos está en terraform.tfvars y backend.tf.

locals {
  prefijo = var.project_id # convención: <proyecto>-<tipo>-<propósito>
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
  landing_listadores   = module.iam.equipo_members
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
  }
}
