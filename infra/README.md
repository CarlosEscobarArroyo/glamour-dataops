# Infraestructura (Terraform)

Toda la infraestructura de GCP del pipeline se define aquí y se despliega solo
desde GitHub Actions ([`terraform.yml`](../.github/workflows/terraform.yml)).
Nadie crea ni cambia recursos a mano en la consola: un cambio entra por pull request.

## Estructura

```text
infra/
├── bootstrap/            Se corre una vez por proyecto, a mano: APIs, bucket del
│                         estado, sa-terraform-<ambiente> y Workload Identity Federation.
├── modules/
│   ├── iam/              Cuentas de servicio y roles de proyecto (pipeline y equipo).
│   ├── vpc/              VPC, subred, Cloud Router, IP fija y Cloud NAT.
│   ├── secrets/          Los secretos MYSQL_HOST y MYSQL_PASSWORD (vacíos) y quién los lee.
│   ├── storage/          Landing zone (Parquet) y bucket de Data Docs.
│   ├── bigquery/         Datasets staging, validation y dimensional, con sus accesos.
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
| `sa-extraction-<ambiente>` | Crear objetos (no borrar ni sobrescribir) | Bucket landing |
| | Leer el valor | Secretos `MYSQL_HOST` y `MYSQL_PASSWORD` |
| `sa-quality-<ambiente>` | Leer tablas y ejecutar consultas | Datasets `bq_staging` y `bq_validation` |
| | Escribir Data Docs | Bucket de Data Docs |
| `sa-workflows-<ambiente>` | Ejecutar los Jobs | Proyecto (los Jobs los crea el CI) |
| | Leer Parquet | Bucket landing |
| | Editar tablas y ejecutar consultas | Datasets `bq_staging`, `bq_validation` y `bq_dimensional` |
| `sa-scheduler-<ambiente>` | Iniciar ejecuciones del workflow | Proyecto |
| `sa-looker-<ambiente>` | Leer tablas | Solo `bq_dimensional` |
| `sa-deploy-<ambiente>` | Publicar imágenes, desplegar Jobs, publicar el workflow, cargar `ref_ubigeo` y publicar los procedimientos SQL | Repositorio de imágenes, proyecto y datasets `bq_staging` y `bq_validation`; solo desde el environment de GitHub de su ambiente |
| `sa-terraform-<ambiente>` | Administrar la plataforma (sin `owner`) | Proyecto; solo la usa GitHub Actions |

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

2. En GitHub, *Settings > Secrets and variables > Actions > Variables*, crear a
   nivel de repositorio, con los outputs del paso 1:

   | Variable | Valor |
   | --- | --- |
   | `WIF_PROVIDER_DEV` / `WIF_PROVIDER_PROD` | output `wif_provider` |
   | `TF_SA_DEV` / `TF_SA_PROD` | output `terraform_sa_email` |

3. En *Settings > Environments*, crear `dev` y `prod`. A `prod` agregarle
   revisores obligatorios: así ningún `apply` ni despliegue llega a producción sin
   aprobación. En cada environment, crear las variables que usa
   [`jobs.yml`](../.github/workflows/jobs.yml):

   | Variable | Valor (dev) |
   | --- | --- |
   | `PROJECT_ID` | `glamour-dataops-dev` |
   | `REGION` | `us-east1` |
   | `WIF_PROVIDER` | output `wif_provider` del paso 1 |
   | `DEPLOY_SA` | `sa-deploy-dev@glamour-dataops-dev.iam.gserviceaccount.com` |

4. Si un secreto (`MYSQL_HOST` o `MYSQL_PASSWORD`) ya existe en el proyecto,
   importarlo antes del primer `apply` para que Terraform no intente crearlo de
   nuevo. Ejemplo con `MYSQL_PASSWORD`:

   ```bash
   cd infra/environments/dev
   terraform init
   terraform import 'module.secrets.google_secret_manager_secret.secreto["MYSQL_PASSWORD"]' projects/glamour-dataops-dev/secrets/MYSQL_PASSWORD
   ```

5. Hacer merge a `dev`. GitHub Actions aplica la infraestructura y después
   `jobs.yml` puede desplegar los Jobs.

6. Si un secreto es nuevo, cargar su valor (nunca en el repo ni en Terraform).
   Repetir para `MYSQL_HOST` y `MYSQL_PASSWORD`:

   ```bash
   printf '%s' 'valor' | gcloud secrets versions add MYSQL_PASSWORD --data-file=- --project=glamour-dataops-dev
   ```

7. Pedir al proveedor de MariaDB que autorice la IP del output
   `ip_para_firewall_mariadb` en el puerto 3306, para un usuario de solo lectura.

## Flujo de trabajo

| Evento | Qué hace |
| --- | --- |
| Pull request a `dev` o `main` | `fmt`, `validate` y `plan`; el plan queda en el resumen del run |
| Merge a `dev` | `apply` en `glamour-dataops-dev` |
| Merge a `main` | `apply` en `glamour-dataops-prod`, después de la aprobación |

Se dispara con cambios en `infra/`.

## Acuerdos con los otros frentes

- **Jobs (CI/CD):** Terraform no crea los Cloud Run Jobs. Los despliega
  [`jobs.yml`](../.github/workflows/jobs.yml) desde `src/<componente>/job.yaml`, con
  la imagen publicada en `<region>-docker.pkg.dev/<proyecto>/<proyecto>-ar-jobs/`
  (ver `docs/artifact_registry.md`). Terraform aporta la red, las cuentas, el
  secreto, el bucket y el repositorio de imágenes que ese archivo referencia.
- **Orquestación:** Terraform crea el workflow con su cuenta, sus variables y el
  flujo provisional de `modules/orchestration/provisional.yaml`, y no vuelve a tocar
  su contenido. La definición real, `src/orchestration/workflow_comercial.yaml`, la
  publica [`orchestration.yml`](../.github/workflows/orchestration.yml).
  El flujo recibe por `sys.get_env` los nombres de los Jobs, del bucket y de los datasets.

## Protecciones

- Bucket landing, datasets e IP del NAT con `prevent_destroy`: un `apply`
  equivocado no puede borrarlos.
- Landing con política de retención: un Parquet no puede borrarse ni reemplazarse
  antes de N días (1 en dev, 30 en prod).
- Buckets con acceso público bloqueado y permisos solo por IAM.
- Sin llaves JSON: GitHub Actions entra por Workload Identity Federation,
  limitado a este repositorio.
