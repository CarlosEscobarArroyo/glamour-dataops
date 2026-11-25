variable "project_id" {
  description = "Proyecto de GCP (glamour-dataops-dev o glamour-dataops-prd)."
  type        = string
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "github_repo" {
  description = "Repositorio autorizado a desplegar, como dueño/nombre."
  type        = string
  default     = "CarlosEscobarArroyo/glamour-dataops"
}
