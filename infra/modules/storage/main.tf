# Landing zone (Parquet del extractor) y bucket de Data Docs de Great Expectations.

resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-landing"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # El extractor nunca sobrescribe (if_generation_match=0). Esta retención impide
  # además borrar o reemplazar un Parquet antes de que cumpla los días indicados.
  retention_policy {
    retention_period = var.retencion_dias * 86400
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket" "data_docs" {
  name                        = "${var.project_id}-data-docs"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # es un reporte regenerable
}

# Accesos por bucket: cada cuenta solo ve el bucket que necesita.
resource "google_storage_bucket_iam_member" "landing_escritura" {
  for_each = var.landing_escritores
  bucket   = google_storage_bucket.landing.name
  role     = "roles/storage.objectCreator" # crear, no borrar ni sobrescribir
  member   = each.value
}

resource "google_storage_bucket_iam_member" "landing_lectura" {
  for_each = var.landing_lectores
  bucket   = google_storage_bucket.landing.name
  role     = "roles/storage.objectViewer"
  member   = each.value
}

resource "google_storage_bucket_iam_member" "landing_listado" {
  for_each = var.landing_listadores
  bucket   = google_storage_bucket.landing.name
  role     = "roles/storage.legacyBucketReader" # ver y listar, sin abrir los archivos
  member   = each.value
}

resource "google_storage_bucket_iam_member" "data_docs_escritura" {
  for_each = var.data_docs_escritores
  bucket   = google_storage_bucket.data_docs.name
  role     = "roles/storage.objectUser" # Data Docs reescribe su index.html
  member   = each.value
}
