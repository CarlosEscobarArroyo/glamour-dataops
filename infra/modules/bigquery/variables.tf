variable "location" {
  type = string
}

variable "staging_editores" {
  type    = map(string)
  default = {}
}

variable "staging_lectores" {
  type    = map(string)
  default = {}
}

variable "validation_editores" {
  type    = map(string)
  default = {}
}

variable "validation_lectores" {
  type    = map(string)
  default = {}
}

variable "dimensional_editores" {
  type    = map(string)
  default = {}
}

variable "dimensional_lectores" {
  type    = map(string)
  default = {}
}
