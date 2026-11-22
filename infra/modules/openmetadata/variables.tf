variable "prefijo" {
  type = string
}

variable "ambiente" {
  type = string
}

variable "region" {
  type = string
}

variable "zona" {
  type = string
}

variable "network_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "tipo_maquina" {
  description = "El mínimo de OpenMetadata es 4 vCPU y 6 GB de RAM."
  type        = string
  default     = "e2-standard-4"
}

variable "disco_gb" {
  type    = number
  default = 50
}
