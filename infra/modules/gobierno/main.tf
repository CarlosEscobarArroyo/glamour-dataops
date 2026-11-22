# Protección de los datos personales de las vendedoras (correo, teléfonos,
# contraseña, documentos y dirección) con seguridad a nivel de columna. Una
# columna con la policy tag "dato_personal" se lee así:
#   - lectores_reales: ven el valor real.
#   - lectores_enmascarados: ven NULL.
#   - el resto: la consulta falla si pide esa columna.
# Ni roles/owner ni roles/bigquery.admin dan acceso por sí solos: hay que estar
# en lectores_reales.
#
# Aquí solo se crea la etiqueta y sus permisos. Ponerla en las columnas es tarea
# del workflow (src/orchestration/workflow_comercial.yaml), porque cada carga
# reemplaza las tablas y borra las etiquetas.

resource "google_data_catalog_taxonomy" "datos_personales" {
  region                 = var.location
  display_name           = "${var.prefijo}-datos-personales"
  description            = "Clasificación de los datos personales de las vendedoras."
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]
}

resource "google_data_catalog_policy_tag" "dato_personal" {
  taxonomy     = google_data_catalog_taxonomy.datos_personales.id
  display_name = "dato_personal"
  description  = "Correo, teléfonos, contraseña, documentos y dirección. Solo los administradores ven el valor real."
}

resource "google_data_catalog_policy_tag_iam_member" "lectores_reales" {
  for_each   = var.lectores_reales
  policy_tag = google_data_catalog_policy_tag.dato_personal.name
  role       = "roles/datacatalog.categoryFineGrainedReader"
  member     = each.value
}

# Se enmascara con NULL y no con un hash: un celular tiene 9 dígitos y su SHA-256
# se revierte probando todas las combinaciones.
resource "google_bigquery_datapolicy_data_policy" "nulo" {
  location         = var.location
  data_policy_id   = "dato_personal_nulo"
  policy_tag       = google_data_catalog_policy_tag.dato_personal.name
  data_policy_type = "DATA_MASKING_POLICY"

  data_masking_policy {
    predefined_expression = "ALWAYS_NULL"
  }
}

resource "google_bigquery_datapolicy_data_policy_iam_member" "lectores_enmascarados" {
  for_each       = var.lectores_enmascarados
  location       = google_bigquery_datapolicy_data_policy.nulo.location
  data_policy_id = google_bigquery_datapolicy_data_policy.nulo.data_policy_id
  role           = "roles/bigquerydatapolicy.maskedReader"
  member         = each.value
}

# Para poner la etiqueta en una columna hace falta ver la taxonomía y el permiso
# bigquery.tables.setCategory, que dataEditor no incluye y dataOwner sí.
resource "google_data_catalog_taxonomy_iam_member" "etiquetadores" {
  for_each = var.etiquetadores
  taxonomy = google_data_catalog_taxonomy.datos_personales.name
  region   = var.location
  role     = "roles/datacatalog.viewer"
  member   = each.value
}

resource "google_bigquery_dataset_iam_member" "etiquetadores" {
  for_each = {
    for par in setproduct(keys(var.etiquetadores), var.datasets) :
    "${par[0]}-${par[1]}" => { member = var.etiquetadores[par[0]], dataset = par[1] }
  }

  dataset_id = each.value.dataset
  role       = "roles/bigquery.dataOwner"
  member     = each.value.member
}
