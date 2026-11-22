output "policy_tag" {
  description = "Nombre completo de la policy tag, como lo pide la API de BigQuery."
  value       = google_data_catalog_policy_tag.dato_personal.name
}
