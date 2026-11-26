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
│   ├── iam/              Cuentas de servicio y roles de proyecto del pipeline.
│   ├── vpc/              VPC, subred, Cloud Router, IP fija y Cloud NAT.
│   ├── secrets/          Los secretos MYSQL_HOST y MYSQL_PASSWORD (vacíos) y quién los lee.
│   ├── storage/          Landing zone (Parquet) y bucket de Data Docs.
│   ├── bigquery/         Datasets staging, validation y dimensional, con sus accesos.
│   ├── gobierno/         Policy tag y enmascarado de los datos personales de las vendedoras.
│   ├── orchestration/    Cloud Workflows y Cloud Scheduler (5:00 a. m., Lima).
│   └── openmetadata/     VM para OpenMetadata con IP fija; interfaz pública, SSH por IAP.
└── environments/
    ├── dev/              glamour-dataops-dev  (rama dev)
    └── prd/             glamour-dataops-prd (rama prd)
```

`main.tf` es igual en `dev` y `prd`; lo que cambia está en `terraform.tfvars`
y `backend.tf`.

## Cuentas de servicio

| Cuenta | Puede | Sobre |
| --- | --- | --- |
| `sa-extraction-<ambiente>` | Crear objetos (no borrar ni sobrescribir) | Bucket landing |
| | Leer el valor | Secretos `MYSQL_HOST` y `MYSQL_PASSWORD` |
| `sa-quality-<ambiente>` | Leer tablas y ejecutar consultas | Datasets `bq_staging` y `bq_validation` |
| | Leer resultados grandes con la API de lectura de BigQuery | Proyecto (`roles/bigquery.readSessionUser`) |
| | Escribir Data Docs | Bucket de Data Docs |
| `sa-workflows-<ambiente>` | Ejecutar los Jobs y consultar su estado | Proyecto (los Jobs los crea el CI) |
| | Leer Parquet | Bucket landing |
| | Editar tablas y ejecutar consultas | Datasets `bq_staging`, `bq_validation` y `bq_dimensional` |
| `sa-scheduler-<ambiente>` | Iniciar ejecuciones del workflow | Proyecto |
| `sa-looker-<ambiente>` | Leer tablas | Solo `bq_dimensional` |
| `sa-deploy-<ambiente>` | Publicar imágenes, desplegar Jobs, publicar el workflow, cargar `ref_ubigeo` y publicar los procedimientos SQL | Repositorio de imágenes, proyecto y datasets `bq_staging` y `bq_validation`; solo desde el environment de GitHub de su ambiente |
| `sa-terraform-<ambiente>` | Administrar la plataforma (sin `owner`) | Proyecto; solo la usa GitHub Actions |

Los accesos de los integrantes (roles de la sección 7 del README principal)
se dan a mano en la consola, no con Terraform.

## Puesta en marcha (una vez por proyecto)

1. Bootstrap, con la cuenta de un integrante con permisos de propietario:

   ```bash
   cd infra/bootstrap
   gcloud auth application-default login
   terraform init
   terraform apply -var="project_id=glamour-dataops-dev"
   ```

   Su estado queda local (`terraform.tfstate`, ignorado por git). Para `prd`,
   repetir en otra carpeta o con `terraform workspace new prd`.

2. En GitHub, *Settings > Secrets and variables > Actions > Variables*, crear a
   nivel de repositorio, con los outputs del paso 1:

   | Variable | Valor |
   | --- | --- |
   | `WIF_PROVIDER_DEV` / `WIF_PROVIDER_PRD` | output `wif_provider` |
   | `TF_SA_DEV` / `TF_SA_PRD` | output `terraform_sa_email` |

3. En *Settings > Environments*, crear `dev` y `prd`. A `prd` agregarle
   revisores obligatorios: así ningún `apply` ni despliegue llega a producción sin
   aprobación. En cada environment, crear las variables que usa
   [`deploy-jobs.yml`](../.github/workflows/deploy-jobs.yml):

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
   `deploy-jobs.yml` puede desplegar los Jobs.

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
| Pull request a `dev` o `prd` | `fmt`, `validate` y `plan`; el plan queda en el resumen del run |
| Merge a `dev` | `apply` en `glamour-dataops-dev` |
| Merge a `prd` | `apply` en `glamour-dataops-prd`, después de la aprobación |

Se dispara con cambios en `infra/`.

## Acuerdos con los otros frentes

- **Jobs (CI/CD):** Terraform no crea los Cloud Run Jobs. Los despliega
  [`deploy-jobs.yml`](../.github/workflows/deploy-jobs.yml) desde `src/<componente>/job.yaml`, con
  la imagen publicada en `<region>-docker.pkg.dev/<proyecto>/<proyecto>-ar-jobs/`
  (ver `docs/artifact_registry.md`). Terraform aporta la red, las cuentas, el
  secreto, el bucket y el repositorio de imágenes que ese archivo referencia.
- **Orquestación:** Terraform crea el workflow con su cuenta, sus variables y el
  flujo provisional de `modules/orchestration/provisional.yaml`, y no vuelve a tocar
  su contenido. La definición real, `src/orchestration/workflow_comercial.yaml`, la
  publica [`orchestration.yml`](../.github/workflows/orchestration.yml).
  El flujo recibe por `sys.get_env` los nombres de los Jobs, del bucket y de los datasets.

## OpenMetadata

Se crea solo donde `openmetadata = true` en `terraform.tfvars` (hoy, dev).
Terraform solo crea la VM con una IP fija; Docker y OpenMetadata se instalan a
mano, entrando con el comando del output `openmetadata_ssh`.

La interfaz queda en la dirección del output `openmetadata_url`, abierta a todo
internet por HTTP: hay que cambiar la contraseña del usuario `admin` apenas se
instale. El SSH solo entra por IAP.

Los metadatos viven en el disco de la VM: si Terraform la recrea o la destruye,
se pierden.

## Datos personales

El correo, los teléfonos, la contraseña, el DNI, el RUC y la dirección de
`bq_staging.persona`, y el `celular` de `dim_vendedor`, llevan la policy tag
`dato_personal`:

| Quién | Qué ve |
| --- | --- |
| Dueños del proyecto (`roles/owner`) y `sa-workflows` | El valor real |
| `sa-looker` y `sa-quality` | `NULL` |
| El resto | La consulta falla si pide esas columnas |

- Terraform lee quién es dueño al aplicar: si cambia, hay que volver a aplicar.
- Para que un integrante vea `NULL` en vez de un error, se le da a mano
  `roles/bigquerydatapolicy.maskedReader` en el proyecto.
- La etiqueta la pone el workflow después de cada carga, porque reemplazar una
  tabla la borra. Entre que termina la carga y se vuelve a poner pasan unos
  segundos en que la columna queda sin proteger. La lista de columnas está en
  `columnas_protegidas`, en `src/orchestration/workflow_comercial.yaml`.
- `bootstrap/` le da a `sa-terraform` las dos APIs y el rol
  `roles/datacatalog.categoryAdmin` que esto necesita.

## Protecciones

- Bucket landing, datasets e IP del NAT con `prevent_destroy`: un `apply`
  equivocado no puede borrarlos.
- Landing con política de retención: un Parquet no puede borrarse ni reemplazarse
  antes de N días (1 en dev, 30 en prd).
- Buckets con acceso público bloqueado y permisos solo por IAM.
- Sin llaves JSON: GitHub Actions entra por Workload Identity Federation,
  limitado a este repositorio.
