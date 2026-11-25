output "ip_para_firewall_mariadb" {
  description = "IP que el proveedor de MariaDB debe autorizar en el puerto 3306."
  value       = module.vpc.nat_ip
}

output "landing_bucket" {
  description = "Bucket de la landing (GCS_BUCKET en src/extraction/job.yaml)."
  value       = module.storage.landing_bucket
}

output "repositorio_imagenes" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.imagenes.repository_id}"
}

output "cuentas_de_servicio" {
  value = module.iam.emails
}

output "openmetadata_url" {
  description = "Interfaz de OpenMetadata, una vez instalado (vacío si no hay VM)."
  value       = one([for vm in module.openmetadata : "http://${vm.ip}:8585"])
}

output "openmetadata_ssh" {
  description = "Comando para entrar a la VM (vacío si no hay VM)."
  value       = one([for vm in module.openmetadata : "gcloud compute ssh ${vm.nombre} --zone=${vm.zona} --project=${var.project_id} --tunnel-through-iap"])
}
