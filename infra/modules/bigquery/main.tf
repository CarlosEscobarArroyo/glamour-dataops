# Dos capas: staging (crudo, aislado del usuario final) y dimensional (lo que ve Looker Studio).

resource "google_bigquery_dataset" "staging" {
  dataset_id                 = "staging"
  location                   = var.location
  description                = "Tablas crudas cargadas desde la landing zone. No se expone a usuarios finales."
  delete_contents_on_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "dimensional" {
  dataset_id                 = "dimensional"
  location                   = var.location
  description                = "Modelo dimensional validado: fact_pedidos y sus dimensiones."
  delete_contents_on_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset_iam_member" "staging_editores" {
  for_each   = var.staging_editores
  dataset_id = google_bigquery_dataset.staging.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = each.value
}

resource "google_bigquery_dataset_iam_member" "staging_lectores" {
  for_each   = var.staging_lectores
  dataset_id = google_bigquery_dataset.staging.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}

resource "google_bigquery_dataset_iam_member" "dimensional_editores" {
  for_each   = var.dimensional_editores
  dataset_id = google_bigquery_dataset.dimensional.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = each.value
}

resource "google_bigquery_dataset_iam_member" "dimensional_lectores" {
  for_each   = var.dimensional_lectores
  dataset_id = google_bigquery_dataset.dimensional.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}
