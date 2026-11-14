output "landing_bucket" {
  value = google_storage_bucket.landing.name
}

output "data_docs_bucket" {
  value = google_storage_bucket.data_docs.name
}
