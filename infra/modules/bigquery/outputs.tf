output "staging_dataset" {
  value = google_bigquery_dataset.staging.dataset_id
}

output "dimensional_dataset" {
  value = google_bigquery_dataset.dimensional.dataset_id
}
