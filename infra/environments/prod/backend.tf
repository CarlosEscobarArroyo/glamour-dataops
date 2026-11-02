# El bucket lo crea infra/bootstrap. Un backend no acepta variables: va escrito.
terraform {
  backend "gcs" {
    bucket = "glamour-dataops-prod-tfstate"
    prefix = "infra"
  }
}
