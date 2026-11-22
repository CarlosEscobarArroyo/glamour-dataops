# Calidad de datos con Great Expectations

Cloud Run Job que valida el modelo recién construido en `bq_validation`. Lo
ejecuta el paso `validar_calidad` de
[`workflow_comercial.yaml`](../orchestration/workflow_comercial.yaml), después de
construir el modelo y antes de publicarlo. Un rechazo detiene el workflow: el
modelo candidato no se copia a `bq_dimensional`, que conserva su última versión
aprobada. El workflow le pasa `RUN_ID`, el mismo identificador de la carpeta de
la extracción en la landing.

## Alcance

Las once tablas del modelo tienen un contrato estructural: tabla no vacía,
columnas exactas, clave no nula y clave única. El piloto añade reglas de negocio
para `dim_fecha`, `dim_campana`, `dim_ubicacion`, `dim_vendedor` y
`fact_pedidos`. `dim_fecha` completa el piloto descrito en el informe porque es
una dependencia directa de las fechas del hecho de pedidos.

Las reglas que aún requieren confirmación de negocio no se incluyen en esta versión:
montos negativos, coordinadoras o líderes ausentes y relaciones de productos
históricos. Se incorporarán después de medirlas en dev.

## Reglas críticas y advertencias

Una regla es **crítica** por defecto: si falla, el Job termina con código `1` y,
una vez conectado al workflow, el modelo no se publica. Las reglas con
`severity="warning"` son **advertencias**: aparecen en Data Docs (su descripción
empieza con "Advertencia:") y en el log, pero no bloquean. Una advertencia que no
se pudo ejecutar, por ejemplo por un error en su consulta, sí bloquea.

Son advertencias los defectos del origen medidos en la ejecución del 22/11/2026,
que corresponde corregir en la transformación:

| Tabla | Regla | Filas | Corrección pendiente |
| --- | --- | ---: | --- |
| `fact_pedidos` | Cada pedido tiene su vendedora en `dim_vendedor` | 71 | Definir qué hacer con pedidos de clientes que no son asesoras ni líderes, o que no existen en `persona` |
| `fact_pedidos` | `estado_pedido` tiene un nombre conocido | 8 | `fact_pedidos.sql` deja pasar el código de los estados que no traduce |
| `dim_campana` | La fecha inicial no es posterior a la final | 1 | Agregar la campaña a las correcciones a mano de `dim_campana.sql` |
| `dim_ubicacion` | Los departamentos del Perú tienen nombre | 1 | `PE030000` no tiene departamento en `ref_ubigeo.csv` (Apurímac) |

Cuando se corrija una, la regla vuelve a ser crítica: quitar su `severity`.

En `dim_ubicacion`, los códigos que terminan en `0000` son un país o un
departamento y no tienen distrito ni provincia. Por eso se exige distrito,
provincia y departamento solo a los códigos de distrito.

## Configuración

| Variable | Uso | Obligatoria |
| --- | --- | --- |
| `GCP_PROJECT` | Proyecto de BigQuery y de Cloud Storage | Sí |
| `BQ_DATASET` | Dataset del modelo candidato (`bq_validation`) | Sí |
| `DATA_DOCS_BUCKET` | Bucket privado donde se publican los reportes | Sí |
| `RUN_ID` | Correlación con una ejecución del workflow | No; se genera para ejecuciones manuales |

Cloud Run usa las credenciales de `sa-quality-<ambiente>`. No hay credenciales
ni secretos dentro de la imagen.

## Resultado

El proceso termina con código `0` si todas las expectativas pasan y `1` ante un
rechazo o error técnico. Los Data Docs se generan localmente y se publican en:

```text
gs://<bucket>/runs/<RUN_ID>/
gs://<bucket>/latest/
```

El resultado usa formato resumido y no incluye filas ni valores inesperados para
evitar que los reportes expongan datos personales. El log del Job registra una
línea `quality_table` por tabla con sus reglas críticas fallidas y sus
advertencias.

`latest/` se vacía antes de cada publicación, así que solo muestra la última
ejecución. El historial queda en `runs/`.

### Cómo ver los reportes

El bucket es privado. Abrir en el navegador, con una cuenta con lectura sobre el
bucket:

```text
https://storage.cloud.google.com/<bucket>/latest/index.html
```

Cloud Storage redirige a `googleusercontent.com` con la ruta codificada, donde un
enlace relativo pierde la carpeta y da Not Found. Por eso el Job reescribe los
enlaces de cada página como direcciones completas de `storage.cloud.google.com`,
que vuelven a pasar por la autenticación. Si el navegador tiene varias cuentas de
Google iniciadas y un enlace devuelve un error de permisos, agregar
`?authuser=<n>` con el número de la cuenta correcta.

## Pruebas

Las pruebas son unitarias y no acceden a BigQuery ni Cloud Storage:

```bash
python -m pip install -r src/quality/requirements.txt
python -B -m unittest discover -s tests/quality -v
```

Para probar un cambio en las reglas sin correr todo el pipeline, ejecutar el Job
a mano en dev después del despliegue. Calibrar primero ahí: una regla crítica mal
calibrada detendría la publicación diaria.

## Agregar una tabla o regla

1. Agregar el contrato a `TABLE_CONTRACTS` en `suites.py`.
2. Si necesita reglas profundas, crear su función y registrarla en
   `PILOT_BUILDERS`. Una regla que mide un defecto conocido y no debe detener la
   publicación lleva `severity="warning"` y una descripción que empieza con
   `WARNING_PREFIX`.
3. Agregar o ajustar las pruebas.
4. Validar primero en dev. Una expectativa demasiado estricta detendría la
   publicación diaria.
