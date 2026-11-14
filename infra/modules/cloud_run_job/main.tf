# Un Cloud Run Job genérico: se usa para el extractor y para el de calidad.
#
# La imagen la publica el pipeline de contenedores (frente CI/CD) con
#   gcloud run jobs update <job> --image <imagen:tag>
# Por eso Terraform solo pone la imagen la primera vez e ignora sus cambios después:
# así un apply no devuelve el Job a una versión vieja.

resource "google_cloud_run_v2_job" "job" {
  name                = var.nombre
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    task_count = 1

    template {
      service_account = var.service_account
      timeout         = var.timeout
      max_retries     = var.max_retries

      containers {
        image = var.imagen

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memoria
          }
        }

        dynamic "env" {
          for_each = var.env
          content {
            name  = env.key
            value = env.value
          }
        }
      }

      # Salida directa por la VPC: todo el tráfico pasa por el Cloud NAT de IP fija.
      dynamic "vpc_access" {
        for_each = var.subnet_id == null ? [] : [1]
        content {
          egress = "ALL_TRAFFIC"
          network_interfaces {
            network    = var.network_id
            subnetwork = var.subnet_id
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

# Quién puede ejecutarlo (Cloud Workflows), solo sobre este Job.
resource "google_cloud_run_v2_job_iam_member" "ejecutor" {
  for_each = var.ejecutores
  name     = google_cloud_run_v2_job.job.name
  location = google_cloud_run_v2_job.job.location
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = each.value
}
