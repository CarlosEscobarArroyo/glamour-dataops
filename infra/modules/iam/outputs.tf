output "emails" {
  value = { for k, sa in google_service_account.sa : k => sa.email }
}

output "members" {
  description = "Miembros IAM listos para usar, como serviceAccount:sa-extractor@..."
  value       = { for k, sa in google_service_account.sa : k => sa.member }
}

output "equipo_members" {
  value = { for e in var.equipo : e => "user:${e}" }
}
