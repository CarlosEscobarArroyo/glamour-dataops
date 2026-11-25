# Estos dos valores van como variables del environment en GitHub (ver infra/README.md).
output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "terraform_sa_email" {
  value = google_service_account.terraform.email
}

output "tfstate_bucket" {
  value = google_storage_bucket.tfstate.name
}
