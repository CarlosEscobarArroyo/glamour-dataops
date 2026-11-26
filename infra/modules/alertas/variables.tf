variable "prefijo" {
  type = string
}

variable "workflow" {
  description = "Nombre del workflow del pipeline."
  type        = string
}

variable "vm_openmetadata" {
  description = "Nombre de la VM de OpenMetadata; null si el ambiente no la tiene."
  type        = string
  default     = null
}

variable "canal" {
  description = "Nombre del canal de correo, creado a mano en el proyecto."
  type        = string
  default     = "Correo"
}
