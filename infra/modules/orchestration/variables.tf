variable "nombre" {
  type = string
}

variable "region" {
  type = string
}

variable "workflows_sa" {
  type = string
}

variable "scheduler_sa" {
  type = string
}

variable "definicion" {
  description = "YAML del flujo. Si es null, se usa provisional.yaml."
  type        = string
  default     = null
}

variable "variables" {
  description = "Variables que el flujo lee con sys.get_env (nombres de Jobs, datasets, etc.)."
  type        = map(string)
  default     = {}
}

variable "horario" {
  type    = string
  default = "0 5 * * *"
}

variable "zona_horaria" {
  type    = string
  default = "America/Lima"
}

variable "pausado" {
  description = "true deja el disparo diario detenido (útil en dev)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  type    = bool
  default = true
}
