# El bucket lo crea infra/bootstrap. Un backend no acepta variables: va escrito.
terraform {
  backend "gcs" {
    bucket = "glamour-dataops-dev-tfstate"
    prefix = "infra"
  }
}
