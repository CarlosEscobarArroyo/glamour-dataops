# Permisos de BigQuery y Data Catalog para OpenMetadata

resource "google_project_iam_member" "bigquery" {
  for_each = toset([
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/bigquery.resourceViewer",
    "roles/datacatalog.viewer"
  ])

  project = google_service_account.vm.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.vm.email}"
}

