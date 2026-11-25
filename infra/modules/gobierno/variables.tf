variable "prefijo" {
  type = string
}

variable "location" {
  description = "Ubicación de la taxonomía: la misma de los datasets, en minúsculas (us)."
  type        = string
}

variable "lectores_reales" {
  description = "Ven los datos personales sin enmascarar."
  type        = map(string)
  default     = {}
}

variable "lectores_enmascarados" {
  description = "Ven NULL en los datos personales."
  type        = map(string)
  default     = {}
}

variable "etiquetadores" {
  description = "Pueden poner la policy tag en las columnas de los datasets."
  type        = map(string)
  default     = {}
}

variable "datasets" {
  description = "Datasets donde los etiquetadores ponen la policy tag."
  type        = list(string)
  default     = []
}
