# Alertas de Cloud Monitoring del pipeline. El canal de correo se crea a mano en cada
# proyecto (así la dirección no queda en el repo) y aquí solo se busca por su nombre.

data "google_monitoring_notification_channel" "correo" {
  display_name = var.canal
  type         = "email"
}

# Una ejecución del workflow que termina en FAILED: el pipeline diario no publicó.
resource "google_monitoring_alert_policy" "pipeline_fallido" {
  display_name          = "${var.prefijo}-alerta-pipeline-fallido"
  combiner              = "OR"
  severity              = "ERROR"
  notification_channels = [data.google_monitoring_notification_channel.correo.name]

  conditions {
    display_name = "Workflow - Ejecución fallida"

    condition_threshold {
      filter          = "resource.type = \"workflows.googleapis.com/Workflow\" AND resource.labels.workflow_id = \"${var.workflow}\" AND metric.type = \"workflows.googleapis.com/finished_execution_count\" AND metric.labels.status = \"FAILED\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  # La API exige contenido y tipo juntos: una documentación con solo el asunto falla al crear.
  documentation {
    subject   = "ALERTA - Fallo en pipeline Glamour DataOps"
    mime_type = "text/markdown"
    content   = "Una ejecución del workflow ${var.workflow} terminó en FAILED: el pipeline no publicó datos nuevos y el modelo dimensional conserva la última versión válida.\n\nRevisar la ejecución en Cloud Workflows y los logs del Job que falló (extracción o calidad)."
  }

  alert_strategy {
    notification_prompts = ["OPENED"]
  }
}

# Memoria de la VM de OpenMetadata por encima de 14 GiB (la máquina tiene 16).
resource "google_monitoring_alert_policy" "openmetadata_memoria" {
  count                 = var.vm_openmetadata == null ? 0 : 1
  display_name          = "${var.prefijo}-alerta-openmetadata-memoria"
  combiner              = "OR"
  severity              = "WARNING"
  notification_channels = [data.google_monitoring_notification_channel.correo.name]

  conditions {
    display_name = "OpenMetadata VM - Memoria alta"

    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"compute.googleapis.com/instance/memory/balloon/ram_used\" AND metric.labels.instance_name = \"${var.vm_openmetadata}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 15032385536
      duration        = "300s"

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  documentation {
    subject   = "ALERTA - Memoria alta en OpenMetadata"
    mime_type = "text/markdown"
    content   = "La memoria RAM de la VM ${var.vm_openmetadata} ha superado el umbral de 14 GiB.\n\nRevisar el consumo de memoria en Cloud Monitoring y comprobar el estado de los contenedores Docker de OpenMetadata. Identificar posibles procesos con consumo elevado antes de realizar reinicios o modificaciones."
  }

  alert_strategy {
    notification_prompts = ["OPENED"]
  }
}
