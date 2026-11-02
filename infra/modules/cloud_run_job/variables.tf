variable "nombre" {
  type = string
}

variable "region" {
  type = string
}

variable "service_account" {
  description = "Correo de la cuenta de servicio con la que corre el Job."
  type        = string
}

variable "imagen" {
  description = "Imagen inicial. La de ejemplo de Google sirve hasta que CI/CD publique la real."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/job:latest"
}

variable "env" {
  type    = map(string)
  default = {}
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memoria" {
  type    = string
  default = "2Gi"
}

variable "timeout" {
  type    = string
  default = "3600s"
}

variable "max_retries" {
  type    = number
  default = 1
}

variable "network_id" {
  type    = string
  default = null
}

variable "subnet_id" {
  description = "Si se indica, el Job sale por esa subred (y su Cloud NAT)."
  type        = string
  default     = null
}

variable "ejecutores" {
  description = "Mapa nombre => miembro IAM que puede ejecutar el Job."
  type        = map(string)
  default     = {}
}

variable "deletion_protection" {
  type    = bool
  default = true
}
