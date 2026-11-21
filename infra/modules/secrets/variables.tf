variable "nombres" {
  description = "Nombres de los secretos; los Jobs los referencian en su job.yaml (secretKeyRef)."
  type        = list(string)
}

variable "lectores" {
  description = "Mapa nombre => miembro IAM que puede leer el valor de todos los secretos."
  type        = map(string)
  default     = {}
}
