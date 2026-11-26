# Las dos alertas de dev se crearon a mano en la consola; estos bloques las adoptan
# sin recrearlas. Solo hacen falta en el primer apply: después se puede borrar el archivo.
import {
  to = module.alertas.google_monitoring_alert_policy.pipeline_fallido
  id = "projects/glamour-dataops-dev/alertPolicies/3926697309903444901"
}

import {
  to = module.alertas.google_monitoring_alert_policy.openmetadata_memoria[0]
  id = "projects/glamour-dataops-dev/alertPolicies/10519877489903678628"
}
