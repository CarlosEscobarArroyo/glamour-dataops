output "ip_para_firewall_mariadb" {
  description = "IP que el proveedor de MariaDB debe autorizar en el puerto 3306."
  value       = module.vpc.nat_ip
}

output "landing_bucket" {
  description = "Valor de GCS_BUCKET en config_dev.json."
  value       = module.storage.landing_bucket
}

output "repositorio_imagenes" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.imagenes.repository_id}"
}

output "cuentas_de_servicio" {
  value = module.iam.emails
}
