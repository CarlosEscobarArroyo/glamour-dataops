# Infraestructura (Terraform)

Toda la infraestructura de GCP del pipeline se define aquí y se despliega solo
desde GitHub Actions ([`terraform.yml`](../.github/workflows/terraform.yml)).
Nadie crea ni cambia recursos a mano en la consola: un cambio entra por pull request.

## Estructura

```text
infra/
├── bootstrap/            Se corre una vez por proyecto, a mano: APIs, bucket del
│                         estado, sa-terraform y Workload Identity Federation.
├── modules/
│   ├── iam/              Cuentas de servicio y roles de proyecto (pipeline y equipo).
│   ├── vpc/              VPC, subred, Cloud Router, IP fija y Cloud NAT.
│   ├── secrets/          Los cinco secretos MYSQL_* (vacíos) y quién los lee.
│   ├── storage/          Landing zone (Parquet) y bucket de Data Docs.
│   ├── bigquery/         Datasets staging y dimensional, con sus accesos.
│   ├── cloud_run_job/    Job genérico (extracción y calidad).
│   └── orchestration/    Cloud Workflows y Cloud Scheduler (5:00 a. m., Lima).
└── environments/
    ├── dev/              glamour-dataops-dev  (rama dev)
    └── prod/             glamour-dataops-prod (rama main)
```

`main.tf` es igual en `dev` y `prod`; lo que cambia está en `terraform.tfvars`
y `backend.tf`.

## Cuentas de servicio

| Cuenta | Puede | Sobre |
| --- | --- | --- |
| `sa-extractor` | Crear objetos (no borrar ni sobrescribir) | Bucket landing |
| | Leer el valor | Los cinco secretos `MYSQL_*` |
| `sa-calidad` | Leer tablas y ejecutar consultas | Dataset `staging` |
| | Escribir Data Docs | Bucket de Data Docs |
| `sa-workflows` | Ejecutar los Jobs | Los dos Cloud Run Jobs |
| | Leer Parquet | Bucket landing |
| | Editar tablas y ejecutar consultas | Datasets `staging` y `dimensional` |
| `sa-scheduler` | Iniciar ejecuciones del workflow | Proyecto |
| `sa-looker` | Leer tablas | Solo `dimensional` |
| `sa-terraform` | Administrar la plataforma (sin `owner`) | Proyecto; solo la usa GitHub Actions |

Los integrantes reciben los roles de la sección 7 del README principal
(variable `equipo` en `terraform.tfvars`).

## Puesta en marcha (una vez por proyecto)

1. Bootstrap, con la cuenta de un integrante con permisos de propietario:

   ```bash
   cd infra/bootstrap
   gcloud auth application-default login
   terraform init
   terraform apply -var="project_id=glamour-dataops-dev"
   ```

   Su estado queda local (`terraform.tfstate`, ignorado por git). Para `prod`,
   repetir en otra carpeta o con `terraform workspace new prod`.

2. En GitHub, *Settings > Secrets and variables > Actions > Variables*, crear
   con los outputs del paso 1:

   | Variable | Valor |
   | --- | --- |
   | `WIF_PROVIDER_DEV` / `WIF_PROVIDER_PROD` | output `wif_provider` |
   | `TF_SA_DEV` / `TF_SA_PROD` | output `terraform_sa_email` |

3. En *Settings > Environments*, crear `dev` y `prod`. A `prod` agregarle
   revisores obligatorios: así ningún `apply` llega a producción sin aprobación.

4. Hacer merge a `dev`. GitHub Actions aplica la infraestructura.

5. Cargar los valores de los secretos (nunca en el repo ni en Terraform):

   ```bash
   printf '%s' 'valor' | gcloud secrets versions add MYSQL_PASSWORD --data-file=- --project=glamour-dataops-dev
   ```

   Repetir con `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_DATABASE` y `MYSQL_PORT`.

6. Pedir al proveedor de MariaDB que autorice la IP del output
   `ip_para_firewall_mariadb` en el puerto 3306, para un usuario de solo lectura.

## Flujo de trabajo

| Evento | Qué hace |
| --- | --- |
| Pull request a `dev` o `main` | `fmt`, `validate` y `plan`; el plan queda en el resumen del run |
| Merge a `dev` | `apply` en `glamour-dataops-dev` |
| Merge a `main` | `apply` en `glamour-dataops-prod`, después de la aprobación |

Se dispara con cambios en `infra/` o en `orchestration/` (el YAML del workflow se
despliega desde aquí).

## Acuerdos con los otros frentes

- **Imágenes (CI/CD):** Terraform crea los Jobs con una imagen de ejemplo y luego
  ignora la imagen. El pipeline de contenedores publica en
  `us-central1-docker.pkg.dev/<proyecto>/glamour/` y actualiza el Job con
  `gcloud run jobs update <job> --image <imagen>`.
- **Orquestación:** el flujo se lee de `orchestration/workflow_comercial.yaml`.
  Mientras no exista, se despliega `modules/orchestration/provisional.yaml`.
  El flujo recibe por `sys.get_env` los nombres de los Jobs, del bucket y de los datasets.
- **Calidad:** el Job recibe `GOOGLE_CLOUD_PROJECT`, `BQ_DATASET` y `DATA_DOCS_BUCKET`.
- **Extracción:** el Job recibe las mismas variables que `config_dev.json`
  (`GCS_BUCKET` sale del output `landing_bucket`).

## Protecciones

- Bucket landing, datasets e IP del NAT con `prevent_destroy`: un `apply`
  equivocado no puede borrarlos.
- Landing con política de retención: un Parquet no puede borrarse ni reemplazarse
  antes de N días (1 en dev, 30 en prod).
- Buckets con acceso público bloqueado y permisos solo por IAM.
- Sin llaves JSON: GitHub Actions entra por Workload Identity Federation,
  limitado a este repositorio.
