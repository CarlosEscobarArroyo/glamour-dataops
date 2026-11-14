# Una cuenta de servicio por pieza del pipeline, con el mínimo de permisos.
# Aquí solo van los roles a nivel de proyecto; los de cada bucket, dataset,
# secreto o Job se dan en su propio módulo, sobre ese recurso.
# Siempre *_iam_member (agrega un permiso), nunca *_iam_policy (reemplaza todo).

locals {
  cuentas = {
    extractor = "Cloud Run Job de extracción (MariaDB a la landing)"
    calidad   = "Cloud Run Job de calidad (Great Expectations)"
    workflows = "Orquestador Cloud Workflows"
    scheduler = "Disparador diario de Cloud Scheduler"
    looker    = "Lectura del modelo dimensional para Looker Studio"
  }

  roles_proyecto = {
    "calidad-jobuser"   = { cuenta = "calidad", rol = "roles/bigquery.jobUser" }
    "workflows-jobuser" = { cuenta = "workflows", rol = "roles/bigquery.jobUser" }
    "workflows-logs"    = { cuenta = "workflows", rol = "roles/logging.logWriter" }
    "scheduler-invoker" = { cuenta = "scheduler", rol = "roles/workflows.invoker" }
    "looker-jobuser"    = { cuenta = "looker", rol = "roles/bigquery.jobUser" }
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
  account_id   = "sa-${each.key}"
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
