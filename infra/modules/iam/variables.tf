variable "project_id" {
  type = string
}

variable "equipo" {
  description = "Correos de los integrantes, con los roles de la sección 7 del README."
  type        = list(string)
  default     = []
}
