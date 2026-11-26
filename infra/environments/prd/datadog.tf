# Datadog lee las métricas del proyecto con esta cuenta, sin llaves: la cuenta de
# Datadog (la misma para toda su organización) la suplanta por tokens de corta duración.
resource "google_service_account" "datadog" {
  project      = var.project_id
  account_id   = "sa-datadog-${module.iam.ambiente}"
  display_name = "Datadog - métricas de Google Cloud (${module.iam.ambiente})"
}

resource "google_project_iam_member" "datadog_metricas" {
  for_each = toset([
    "roles/browser",
    "roles/cloudasset.viewer",
    "roles/compute.viewer",
    "roles/monitoring.viewer",
  ])

  project = google_service_account.datadog.project
  role    = each.value
  member  = google_service_account.datadog.member
}

resource "google_service_account_iam_member" "datadog_token_creator" {
  service_account_id = google_service_account.datadog.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:ddgci-274c055aa995b686279f@datadog-gci-sts-us1-prod.iam.gserviceaccount.com"
}
