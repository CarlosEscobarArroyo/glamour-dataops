variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "retencion_dias" {
  description = "Días que un Parquet de la landing no puede borrarse ni reemplazarse."
  type        = number
  default     = 30
}

# Mapas nombre => miembro IAM, como { extractor = "serviceAccount:x@y" }.
# Las llaves fijas evitan que for_each dependa de valores que solo existen tras el apply.
variable "landing_escritores" {
  type    = map(string)
  default = {}
}

variable "landing_lectores" {
  type    = map(string)
  default = {}
}

variable "landing_listadores" {
  type    = map(string)
  default = {}
}

variable "data_docs_escritores" {
  type    = map(string)
  default = {}
}
