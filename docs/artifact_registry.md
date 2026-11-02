# Imágenes de los Cloud Run Jobs

Convención de nombres para las imágenes de los contenedores del proyecto.
La región está pendiente de definir. Esta documentación no crea recursos ni
publica imágenes. La consulta del 30/10/2026 devolvió `SERVICE_DISABLED` para
Artifact Registry en `glamour-dataops-dev`; no se pudo inventariar sus repositorios.

## Estructura

Un repositorio Docker por proyecto/entorno para los Jobs, con una imagen por
componente. Las versiones de cada imagen se identifican mediante etiquetas.

```text
Proyecto: glamour-dataops-dev
└── Artifact Registry: glamour-dataops-dev-ar-jobs
    ├── extraction
    │   └── git-<commit-completo>-<build-id>
    └── quality (futuro, cuando exista el contenedor)
```

| Elemento | Convención |
| --- | --- |
| Proyecto de desarrollo | `glamour-dataops-dev` |
| Repositorio Docker | `glamour-dataops-dev-ar-jobs` |
| Imagen de extracción | `extraction` (código en `src/extraction/`) |
| Imagen de calidad futura | `quality` (código futuro en `src/quality/`) |
| Etiqueta de build | `git-<commit-completo>-<build-id>` |
| Referencia para desplegar | Imagen con digest `@sha256:<digest>` |

Ruta de una imagen:

```text
<region>-docker.pkg.dev/glamour-dataops-dev/glamour-dataops-dev-ar-jobs/extraction:git-<commit-completo>-<build-id>
```

El repositorio agrupa componentes. No crear repositorios por fecha, commit o
tabla de MariaDB. El contenedor de extracción procesa las 18 tablas; cada tabla
no necesita una imagen propia. Los datos históricos se almacenan en GCS.

## Versionado

- Etiquetas inmutables al crear el repositorio. No reutilizar una etiqueta para
  publicar contenido diferente ni usar `latest` como referencia de despliegue.
- El commit identifica el código. El identificador de build distingue reconstrucciones
  del mismo commit, cuyas dependencias o imagen base podrían producir otro digest.
- Publicar versiones trazables desde un checkout limpio. Los cambios locales sin
  commit no deben etiquetarse como si correspondieran a un commit publicado.
- Desplegar Cloud Run por digest para identificar exactamente la imagen ejecutada.
- Mantener producción en su propio proyecto/repositorio cuando se implemente ese
  entorno, promoviendo la misma imagen validada.

## Región y creación

Usar la región acordada para los Cloud Run Jobs. La elección está pendiente y
no se establece un valor por defecto en los scripts del proyecto.

Una vez definida, habilitar la API y crear un repositorio Docker estándar con
nombre `glamour-dataops-dev-ar-jobs`, en esa región, con etiquetas inmutables.
No configurar borrado automático de versiones hasta definir qué imágenes deben
permanecer disponibles para los Jobs desplegados y su recuperación.

## Construcción y publicación

El Dockerfile existente recibe `src/extraction/` como contexto. Ejemplo desde la
raíz del proyecto, después de crear el repositorio y configurar la autenticación
Docker para su dominio regional:

```bash
# Definir GLAMOUR_REGION, GLAMOUR_COMMIT y GLAMOUR_BUILD_ID para el build.
: "${GLAMOUR_REGION:?Define la región acordada}"
: "${GLAMOUR_COMMIT:?Define el commit completo de un checkout limpio}"
: "${GLAMOUR_BUILD_ID:?Define un identificador único de build}"

GLAMOUR_IMAGE="${GLAMOUR_REGION}-docker.pkg.dev/glamour-dataops-dev/glamour-dataops-dev-ar-jobs/extraction"
GLAMOUR_TAG="git-${GLAMOUR_COMMIT}-${GLAMOUR_BUILD_ID}"

docker build --platform linux/amd64 -t "${GLAMOUR_IMAGE}:${GLAMOUR_TAG}" src/extraction/
docker push "${GLAMOUR_IMAGE}:${GLAMOUR_TAG}"
```

Publicar una imagen no crea ni ejecuta el Job. El despliegue y su programación
son pasos separados. El manejo de fechas cero del extractor sigue pendiente.

## Referencias

- [Nombres de repositorios, imágenes, etiquetas y digests](https://docs.cloud.google.com/artifact-registry/docs/docker/names).
- [Varias imágenes dentro de un repositorio Docker](https://docs.cloud.google.com/artifact-registry/docs/container-concepts).
