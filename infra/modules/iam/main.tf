# Una cuenta de servicio por pieza del pipeline, con el mínimo de permisos.
# Aquí solo van los roles a nivel de proyecto; los de cada bucket, dataset,
# secreto o Job se dan en su propio módulo, sobre ese recurso.
# Siempre *_iam_member (agrega un permiso), nunca *_iam_policy (reemplaza todo).

locals {
  ambiente = regex("[^-]+$", var.project_id) # glamour-dataops-dev -> dev

  cuentas = {
    extraction = "Cloud Run Job de extracción (MariaDB a la landing)"
    quality    = "Cloud Run Job de calidad (Great Expectations)"
    workflows  = "Orquestador Cloud Workflows"
    scheduler  = "Disparador diario de Cloud Scheduler"
    looker     = "Lectura del modelo dimensional para Looker Studio"
    deploy     = "Despliegue de los Jobs, el workflow y el SQL desde GitHub Actions"
  }

  roles_proyecto = {
    "calidad-jobuser"   = { cuenta = "quality", rol = "roles/bigquery.jobUser" }
    "workflows-jobuser" = { cuenta = "workflows", rol = "roles/bigquery.jobUser" }
    "workflows-logs"    = { cuenta = "workflows", rol = "roles/logging.logWriter" }
    "scheduler-invoker" = { cuenta = "scheduler", rol = "roles/workflows.invoker" }
    "looker-jobuser"    = { cuenta = "looker", rol = "roles/bigquery.jobUser" }
    # A nivel de proyecto porque los Jobs los crea el CI, no Terraform.
    "workflows-jobs"   = { cuenta = "workflows", rol = "roles/run.jobsExecutorWithOverrides" }
    "deploy-run"       = { cuenta = "deploy", rol = "roles/run.developer" }
    "deploy-workflows" = { cuenta = "deploy", rol = "roles/workflows.editor" }
    "deploy-bigquery"  = { cuenta = "deploy", rol = "roles/bigquery.jobUser" }
  }

  # Roles del equipo definidos en el README (sección 7): ver y operar, no administrar datos.
  roles_equipo = [
    "roles/browser",
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/run.developer",
    "roles/workflows.admin",
    "roles/secretmanager.viewer",
    "roles/logging.viewer",
  ]
}

resource "google_service_account" "sa" {
  for_each     = local.cuentas
  account_id   = "sa-${each.key}-${local.ambiente}"
  display_name = each.value
}

resource "google_project_iam_member" "sa" {
  for_each = local.roles_proyecto
  project  = var.project_id
  role     = each.value.rol
  member   = google_service_account.sa[each.value.cuenta].member
}

resource "google_project_iam_member" "equipo" {
  for_each = { for par in setproduct(var.equipo, local.roles_equipo) : "${par[0]}|${par[1]}" => par }
  project  = var.project_id
  role     = each.value[1]
  member   = "user:${each.value[0]}"
}

# sa-deploy asigna a cada Job y al workflow su cuenta de ejecución.
resource "google_service_account_iam_member" "deploy_usa" {
  for_each           = toset(["extraction", "quality", "workflows"])
  service_account_id = google_service_account.sa[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.sa["deploy"].member
}

data "google_project" "actual" {
  project_id = var.project_id
}

# Solo un job de GitHub Actions que corre en el environment de este ambiente (dev o
# prod, este último con aprobación) puede actuar como sa-deploy. El pool wif-github
# lo crea infra/bootstrap y ya limita los tokens a este repositorio.
resource "google_service_account_iam_member" "deploy_github" {
  service_account_id = google_service_account.sa["deploy"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.actual.number}/locations/global/workloadIdentityPools/wif-github/attribute.environment/${local.ambiente}"
}
