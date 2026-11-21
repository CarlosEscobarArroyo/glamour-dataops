# Puesta en marcha manual del ambiente dev

Crea a mano, con `gcloud`, lo mínimo que necesita el Job de extracción en
`glamour-dataops-dev`. Es un atajo mientras Terraform (`infra/`) no se aplique: los
nombres son los mismos que usa Terraform, así que después se importan en vez de
recrearse (ver [Migración a Terraform](#migración-a-terraform)).

Requisitos: `gcloud` y `gh` con sesión iniciada, permisos de propietario sobre el
proyecto y el secreto `MYSQL_PASSWORD` ya creado con su valor.

Ejecutar los pasos en orden y en la misma terminal: el paso 1 define variables de
shell (`$P`, `$R`, `$REPO`) que usan los demás.

Convención de nombres: `<proyecto>-<tipo>-<propósito>`. Tipos: `cs` bucket, `ar`
imágenes, `crj` Cloud Run Job, `vpc` red, `snet` subred, `rtr` router, `ip`
dirección, `nat` NAT. Las cuentas de servicio y la identidad federada no llevan el
proyecto por su límite de 30 y 32 caracteres; las cuentas llevan el ambiente al final.

## 1. Variables y APIs

Fija el proyecto por defecto de `gcloud` y habilita las APIs que faltan. Un proyecto
de GCP no acepta llamadas a un servicio hasta que su API está habilitada.

- `run`: Cloud Run, donde corre el Job.
- `iam`: crear cuentas de servicio y la identidad federada.
- `sts` e `iamcredentials`: el intercambio de credenciales de GitHub. `sts` cambia
  el token de GitHub por uno de Google, e `iamcredentials` lo cambia por una
  credencial temporal de la cuenta de despliegue.

Artifact Registry, Secret Manager, Cloud Storage y Compute ya están habilitadas.

```bash
P=glamour-dataops-dev
R=us-east1
REPO=CarlosEscobarArroyo/glamour-dataops
gcloud config set project $P
gcloud services enable run.googleapis.com iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com
```

## 2. Bucket y repositorio de imágenes

El bucket es la landing zone: ahí el extractor escribe los Parquet y el manifiesto.
`--uniform-bucket-level-access` desactiva los permisos por objeto (ACL); el acceso
se controla solo con IAM a nivel de bucket.

El repositorio de Artifact Registry guarda las imágenes Docker de los Jobs, una por
componente. `--immutable-tags` impide volver a publicar una etiqueta existente: una
etiqueta siempre apunta a la misma imagen. Por eso el CI genera una etiqueta nueva
en cada ejecución.

```bash
gcloud storage buckets create gs://$P-cs-landing --location $R --uniform-bucket-level-access
gcloud artifacts repositories create $P-ar-jobs --repository-format docker --location $R --immutable-tags
```

## 3. Red con IP fija de salida

El proveedor de MariaDB solo acepta conexiones desde IP autorizadas, y Cloud Run
sale a internet por defecto desde IP que cambian. La solución es que el Job salga
por una red propia, con una IP pública reservada. Son cinco recursos que dependen
uno del otro, por eso el orden importa.

### 3.1 Red (VPC)

Crea la red privada del proyecto. Una VPC es global: por sí sola no tiene rangos de
IP ni región; solo es el contenedor de las subredes, las rutas y las reglas de
firewall.

- `--subnet-mode custom`: la red nace sin subredes. En modo `auto`, Google crearía
  una subred en cada región del mundo con rangos predefinidos, que no se necesitan
  y luego pueden chocar con otros rangos.

No se crean reglas de firewall: el Job solo inicia conexiones salientes, que una
VPC permite por defecto, y no recibe conexiones entrantes.

```bash
gcloud compute networks create $P-vpc --subnet-mode custom
```

### 3.2 Subred

Crea, dentro de la red, el rango de IP internas de la región `us-east1`. Con
Direct VPC egress, cada ejecución del Job toma una IP interna de esta subred y sale
a través de ella.

- `--network`: la VPC a la que pertenece.
- `--region`: una subred es regional y debe estar en la misma región que el Job.
- `--range 10.10.0.0/24`: 256 direcciones privadas (RFC 1918). Sobra para un Job de
  una tarea; Cloud Run pide como mínimo un `/26`.
- `--enable-private-ip-google-access`: las llamadas a las API de Google (Cloud
  Storage, Secret Manager) viajan por la red interna de Google en vez de salir por
  el NAT. Así la subida de los Parquet no consume ni paga tráfico de NAT.

```bash
gcloud compute networks subnets create $P-snet-$R --network $P-vpc --region $R --range 10.10.0.0/24 --enable-private-ip-google-access
```

### 3.3 Router

Crea un Cloud Router. Cloud NAT no existe como recurso independiente: es una
configuración que vive dentro de un router, así que este es un requisito del paso
3.5. Aquí no intercambia rutas con nada (no hay BGP ni VPN); solo aloja el NAT.

- `--network` y `--region`: un router pertenece a una red y a una región, y solo
  puede dar NAT a las subredes de esa misma región.

```bash
gcloud compute routers create $P-rtr-egress --network $P-vpc --region $R
```

### 3.4 IP pública reservada

Reserva una dirección IPv4 pública estática en la región. Queda asignada al
proyecto hasta que se libere a propósito, aunque ningún recurso la esté usando.
Esta es la IP que verá el servidor de MariaDB como origen de las conexiones.

- `--region`: es una dirección regional (no global), del mismo tipo que usa Cloud NAT.

Mientras no esté en uso tiene un costo pequeño por hora.

```bash
gcloud compute addresses create $P-ip-egress --region $R
```

### 3.5 NAT

Crea la configuración de Cloud NAT dentro del router. El NAT traduce la IP interna
de cada conexión saliente (`10.10.0.x`) a la IP pública reservada, y lleva la
respuesta de vuelta. Solo permite conexiones iniciadas desde adentro: nadie puede
conectarse desde internet hacia el Job.

- `--router`: el router del paso 3.3 que lo aloja.
- `--nat-external-ip-pool`: usa únicamente la IP reservada del paso 3.4. Sin esta
  opción, Google asignaría direcciones automáticas que pueden cambiar.
- `--nat-all-subnet-ip-ranges`: aplica el NAT a todas las subredes de la red en
  esta región, incluidas las que se creen después.

```bash
gcloud compute routers nats create $P-nat-egress --router $P-rtr-egress --region $R --nat-external-ip-pool $P-ip-egress --nat-all-subnet-ip-ranges
```

### 3.6 Consultar la IP

No crea nada: muestra la dirección reservada en el paso 3.4.

- `--format 'value(address)'`: imprime solo la IP, sin el resto de los campos.

```bash
gcloud compute addresses describe $P-ip-egress --region $R --format 'value(address)'
```

Pedir al proveedor de MariaDB que autorice esa IP en el puerto 3306. Si la
dirección se borra, la nueva será otra y habrá que pedir la autorización de nuevo.

### Cómo se conecta con el Job

La red no hace nada hasta que el Job la usa. Eso está en dos anotaciones de
[`job.yaml`](../src/extraction/job.yaml):

- `network-interfaces`: conecta el Job a la red y la subred de este paso.
- `vpc-access-egress: all-traffic`: envía todo el tráfico saliente por la red. Con
  el valor por defecto (`private-ranges-only`), el tráfico hacia internet, incluido
  MariaDB, saldría por las IP variables de Cloud Run y no por el NAT.

## 4. Cuenta del Job

`sa-extraction-dev` es la identidad con la que corre el contenedor. Recibe solo dos
permisos, cada uno sobre un recurso y no sobre el proyecto:

- `secretmanager.secretAccessor` sobre `MYSQL_PASSWORD`: Cloud Run lee el secreto
  con esta cuenta al iniciar la ejecución y lo entrega como variable de entorno.
- `storage.objectCreator` sobre el bucket: puede crear objetos, pero no leerlos,
  borrarlos ni sobrescribirlos. Coincide con el extractor, que sube cada archivo con
  `if_generation_match=0`.

```bash
gcloud iam service-accounts create sa-extraction-dev
gcloud secrets add-iam-policy-binding MYSQL_PASSWORD --member serviceAccount:sa-extraction-dev@$P.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor
gcloud storage buckets add-iam-policy-binding gs://$P-cs-landing --member serviceAccount:sa-extraction-dev@$P.iam.gserviceaccount.com --role roles/storage.objectCreator
```

## 5. Cuenta de despliegue y entrada desde GitHub

GitHub Actions necesita una identidad en GCP para publicar la imagen y desplegar el
Job. Este paso tiene dos partes: crear esa identidad con sus permisos (5.1 a 5.4) y
permitir que GitHub la use sin llaves JSON, con Workload Identity Federation (5.5 a
5.7).

### 5.1 Cuenta de despliegue

Crea la cuenta de servicio `sa-deploy-dev`. Es distinta de `sa-extraction-dev` a
propósito: una despliega y la otra ejecuta, y ninguna tiene los permisos de la otra.
Recién creada no puede hacer nada; los permisos vienen en los pasos siguientes.

```bash
gcloud iam service-accounts create sa-deploy-dev
```

### 5.2 Permiso para desplegar Jobs

Le da `roles/run.developer` sobre el proyecto: crear, actualizar y leer Cloud Run
Jobs. Es lo que usa `gcloud run jobs replace`. No incluye cambiar quién tiene acceso
a un Job (eso es `run.admin`).

- Se da a nivel de proyecto y no de un Job, porque el Job todavía no existe: lo
  crea esta misma cuenta en el primer despliegue.
- `--condition None`: el permiso no lleva condición. Se indica para que `gcloud` no
  lo pregunte de forma interactiva si el proyecto ya tiene permisos condicionales.

```bash
gcloud projects add-iam-policy-binding $P --member serviceAccount:sa-deploy-dev@$P.iam.gserviceaccount.com --role roles/run.developer --condition None
```

No está verificado que este rol alcance para desplegar un Job que referencia
secretos. Si el despliegue del paso 7 falla por permisos, se ajusta aquí.

### 5.3 Permiso para publicar imágenes

Le da `roles/artifactregistry.writer` solo sobre el repositorio `ar-jobs`: subir y
leer imágenes. No puede borrarlas ni tocar otros repositorios del proyecto.

- `--location`: Artifact Registry es regional; identifica dónde está el repositorio.

```bash
gcloud artifacts repositories add-iam-policy-binding $P-ar-jobs --location $R --member serviceAccount:sa-deploy-dev@$P.iam.gserviceaccount.com --role roles/artifactregistry.writer
```

### 5.4 Permiso para asignar la cuenta del Job

Le da `roles/iam.serviceAccountUser` sobre `sa-extraction-dev`. El `job.yaml` dice
que el Job corre como `sa-extraction-dev`; GCP exige que quien despliega tenga
permiso de "actuar como" esa cuenta. Sin esta regla, cualquiera que pudiera
desplegar podría poner su código a correr con una cuenta más poderosa.

- El primer argumento es el recurso sobre el que se da el permiso (la cuenta del
  Job); `--member` es quien lo recibe (la cuenta de despliegue).

```bash
gcloud iam service-accounts add-iam-policy-binding sa-extraction-dev@$P.iam.gserviceaccount.com --member serviceAccount:sa-deploy-dev@$P.iam.gserviceaccount.com --role roles/iam.serviceAccountUser
```

### 5.5 Pool de identidad

Crea el pool `wif-github`: un contenedor de identidades externas a Google. Por sí
solo no confía en nadie; sirve para colgar proveedores y para referirse, en los
permisos, a "las identidades que entraron por aquí".

- `--location global`: los pools de identidad solo existen a nivel global.
- `--display-name`: el nombre visible en la consola.

```bash
gcloud iam workload-identity-pools create wif-github --location global --display-name "GitHub Actions"
```

Si un pool se borra, queda 30 días en papelera y su nombre no se puede reutilizar
en ese tiempo.

### 5.6 Proveedor de identidad

Crea el proveedor `wif-github-oidc` dentro del pool. Declara que se confía en los
tokens OIDC que GitHub emite a cada ejecución de un workflow, y bajo qué reglas.

- `--workload-identity-pool`: el pool del paso 5.5.
- `--issuer-uri`: quién firma los tokens. Google descarga de esa dirección las
  llaves públicas de GitHub y verifica con ellas la firma de cada token.
- `--attribute-mapping`: copia datos del token (`assertion.*`) a atributos que IAM
  puede evaluar. `google.subject` es obligatorio e identifica al emisor;
  `attribute.repository` es el repositorio, `attribute.ref` la rama y
  `attribute.environment` el environment de GitHub en el que corre el job.
- `--attribute-condition`: rechaza todo token que no sea de este repositorio. Es
  indispensable: GitHub firma tokens para cualquier repositorio del mundo, y sin
  esta condición todos serían aceptados por el proveedor.

```bash
gcloud iam workload-identity-pools providers create-oidc wif-github-oidc --location global --workload-identity-pool wif-github --issuer-uri https://token.actions.githubusercontent.com --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.environment=assertion.environment" --attribute-condition "assertion.repository == '$REPO'"
```

### 5.7 Quién puede usar la cuenta de despliegue

Le da `roles/iam.workloadIdentityUser` sobre `sa-deploy-dev` a un conjunto de
identidades del pool: las que tienen `attribute.environment` igual a `dev`. Es el
enlace entre las dos partes de este paso: sin él, GitHub puede autenticarse pero no
puede actuar como ninguna cuenta.

- `principalSet://.../attribute.environment/dev`: todos los tokens aceptados por el
  proveedor cuyo environment es `dev`. Como el proveedor ya solo acepta este
  repositorio, el resultado es: un job de este repositorio que corre en el
  environment `dev`.
- `1048504689427`: el número del proyecto `glamour-dataops-dev`. Los pools se
  identifican por número de proyecto, no por su ID.

```bash
gcloud iam service-accounts add-iam-policy-binding sa-deploy-dev@$P.iam.gserviceaccount.com --role roles/iam.workloadIdentityUser --member "principalSet://iam.googleapis.com/projects/1048504689427/locations/global/workloadIdentityPools/wif-github/attribute.environment/dev"
```

### Qué pasa en cada despliegue

1. El job de GitHub Actions pide su token OIDC a GitHub.
2. Lo presenta a Google; el proveedor verifica la firma y que sea de este repositorio.
3. Google comprueba que el environment sea `dev` y entrega una credencial de
   `sa-deploy-dev` que vence en una hora.
4. Con ella, el workflow publica la imagen (5.3) y despliega el Job (5.2 y 5.4).

## 6. Variables del environment `dev` en GitHub

El workflow [`jobs.yml`](../.github/workflows/jobs.yml) no tiene valores de GCP
escritos: los lee de las variables del environment de GitHub en el que corre
(`dev` para la rama `dev`). No son secretos; son identificadores.

- `PROJECT_ID` y `REGION`: dónde publicar la imagen y desplegar. `PROJECT_ID`
  también rellena los marcadores de `job.yaml`.
- `WIF_PROVIDER` y `DEPLOY_SA`: el proveedor y la cuenta del paso 5, que usa la
  acción `google-github-actions/auth`.

```bash
gh variable set PROJECT_ID --env dev --body $P
gh variable set REGION --env dev --body $R
gh variable set DEPLOY_SA --env dev --body sa-deploy-dev@$P.iam.gserviceaccount.com
gh variable set WIF_PROVIDER --env dev --body projects/1048504689427/locations/global/workloadIdentityPools/wif-github/providers/wif-github-oidc
```

## 7. Desplegar el Job

Un push a `dev` que toque `src/` o `tests/` dispara `jobs.yml`. Para el componente
que cambió:

1. Ejecuta sus pruebas unitarias.
2. Construye la imagen y la publica en Artifact Registry.
3. Reemplaza `${PROJECT_ID}`, `${AMBIENTE}`, `${REGION}` e `${IMAGE}` en
   `src/<componente>/job.yaml`. La imagen se referencia por digest (`sha256`), no
   por etiqueta.
4. Aplica el archivo con `gcloud run jobs replace`, que crea el Job si no existe o
   lo deja idéntico al archivo si ya existe.

Desplegar no ejecuta el Job. Para volver a desplegar sin cambios en el código:

```bash
gh workflow run Jobs --ref dev
```

Si el push incluye cambios en `infra/`, también se dispara el workflow de Terraform
y falla en la autenticación mientras no se haya hecho su bootstrap. Es inofensivo.

## 8. Ejecutar el Job

Lanza una ejecución y espera el resultado. El Job lee las 18 tablas de MariaDB y
escribe los Parquet y `manifest.json` en
`gs://glamour-dataops-dev-cs-landing/date=<fecha>/<ejecución>/`. Requiere que el
proveedor ya haya autorizado la IP del paso 3; si no, falla con
`mysql_connection_failed` en los logs.

```bash
gcloud run jobs execute glamour-dataops-dev-crj-extraction --region us-east1 --wait
```

Para revisar los logs de las ejecuciones:

```bash
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="glamour-dataops-dev-crj-extraction"' --project glamour-dataops-dev --limit 50 --format 'value(jsonPayload)'
```

## Migración a Terraform

Cuando se aplique `infra/`, lo creado aquí no se borra: se importa al estado de
Terraform, que pasa a administrarlo.

1. **Bootstrap** (`infra/bootstrap`): importar antes el pool y el proveedor de
   identidad. Las APIs, el bucket del estado y `sa-terraform-dev` se crean nuevos.
2. **Ambiente** (`infra/environments/dev`): importar el bucket, el repositorio de
   imágenes, la red, la subred, el router, la IP, el NAT, `sa-extraction-dev`,
   `sa-deploy-dev` y el secreto, con bloques `import`.
3. **Revisar el plan**: no debe destruir ningún recurso. Es esperable que ajuste lo
   que aquí no se configuró (retención y bloqueo de acceso público del bucket, logs
   del NAT).
4. **Aplicar**: Terraform crea además BigQuery, el bucket de Data Docs, las demás
   cuentas, Workflows y Scheduler.

Los permisos (`add-iam-policy-binding`) no se importan: Terraform los vuelve a
declarar sin conflicto.

No borrar para recrear la IP (cambia y hay que autorizarla de nuevo) ni el pool de
identidad (queda 30 días en papelera y su nombre no se puede reutilizar).
