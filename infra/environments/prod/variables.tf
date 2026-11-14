variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "equipo" {
  description = "Correos de los integrantes del grupo."
  type        = list(string)
  default     = []
}

variable "retencion_dias" {
  type    = number
  default = 30
}

variable "scheduler_pausado" {
  type    = bool
  default = false
}

variable "proteger" {
  description = "Protección contra borrado de Jobs y del workflow."
  type        = bool
  default     = true
}
