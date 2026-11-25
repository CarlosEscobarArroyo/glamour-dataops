# Cloud Workflows (orquestador) y Cloud Scheduler (disparo diario).
# Terraform crea el workflow con su cuenta y sus variables, y un flujo provisional.
# La definición real vive en src/orchestration/workflow_comercial.yaml y la publica el
# CI (.github/workflows/orchestration.yml), igual que los Jobs.

resource "google_workflows_workflow" "pipeline" {
  name                = var.nombre
  region              = var.region
  service_account     = var.workflows_sa
  call_log_level      = "LOG_ERRORS_ONLY"
  source_contents     = file("${path.module}/provisional.yaml")
  user_env_vars       = var.variables
  deletion_protection = var.deletion_protection

  # El contenido lo publica el CI: Terraform no lo revierte en cada apply.
  lifecycle {
    ignore_changes = [source_contents]
  }
}

resource "google_cloud_scheduler_job" "diario" {
  name      = "${replace(var.nombre, "-wf-", "-sch-")}-daily" # <proyecto>-sch-pipeline-daily
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
