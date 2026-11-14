# Terraform crea los secretos VACÍOS. Los valores se cargan aparte, una sola vez:
#   printf '%s' 'la-clave' | gcloud secrets versions add MYSQL_PASSWORD --data-file=-
# Así ninguna credencial queda en el código ni en el estado de Terraform.

resource "google_secret_manager_secret" "secreto" {
  for_each  = toset(var.nombres)
  secret_id = each.value

  replication {
    auto {}
  }
}

# Acceso secreto por secreto (no a nivel de proyecto).
resource "google_secret_manager_secret_iam_member" "lector" {
  for_each = {
    for par in setproduct(var.nombres, keys(var.lectores)) :
    "${par[0]}|${par[1]}" => { secreto = par[0], member = var.lectores[par[1]] }
  }
  secret_id = google_secret_manager_secret.secreto[each.value.secreto].id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}
