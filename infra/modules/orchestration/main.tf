# Cloud Workflows (orquestador) y Cloud Scheduler (disparo diario).
# La definición del flujo vive en orchestration/workflow_comercial.yaml (frente de
# orquestación); mientras no exista, se despliega un flujo provisional.

resource "google_workflows_workflow" "pipeline" {
  name                = var.nombre
  region              = var.region
  service_account     = var.workflows_sa
  call_log_level      = "LOG_ERRORS_ONLY"
  source_contents     = coalesce(var.definicion, file("${path.module}/provisional.yaml"))
  user_env_vars       = var.variables
  deletion_protection = var.deletion_protection
}

resource "google_cloud_scheduler_job" "diario" {
  name      = "${var.nombre}-diario"
  region    = var.region
  schedule  = var.horario
  time_zone = var.zona_horaria
  paused    = var.pausado

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.pipeline.id}/executions"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ argument = jsonencode({ origen = "scheduler" }) }))

    oauth_token {
      service_account_email = var.scheduler_sa
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
