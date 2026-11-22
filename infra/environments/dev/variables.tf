variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "bq_location" {
  type    = string
  default = "US"
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
  description = "Protección contra borrado del workflow."
  type        = bool
  default     = true
}
