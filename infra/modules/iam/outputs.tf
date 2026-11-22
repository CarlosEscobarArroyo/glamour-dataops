output "emails" {
  value = { for k, sa in google_service_account.sa : k => sa.email }
}

output "members" {
  description = "Miembros IAM listos para usar, como serviceAccount:sa-extraction-dev@..."
  value       = { for k, sa in google_service_account.sa : k => sa.member }
}
