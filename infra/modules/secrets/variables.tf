variable "nombres" {
  description = "Nombres de los secretos; deben coincidir con la sección secrets de config_dev.json."
  type        = list(string)
}

variable "lectores" {
  description = "Mapa nombre => miembro IAM que puede leer el valor de todos los secretos."
  type        = map(string)
  default     = {}
}
