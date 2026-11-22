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

Reglas de negocio de `fact_pedidos`, por tipo de control:

| Control | Reglas |
| --- | --- |
| Completitud | Campaña, vendedora, fecha, estado, montos, `es_nueva_vendedora` y `tipo` no nulos |
| Integridad referencial | Campaña, vendedora, fecha del pedido, fecha de pago, ubicación y coordinadora existen en su dimensión (las tres últimas solo cuando traen valor) |
| Rangos | Montos no negativos; `monto_pagado = monto_total_pedido − monto_comision + monto_envio` (tolerancia de 0,01); ninguna fecha de pedido futura (hora de Lima) |
| Valores permitidos | `estado_pedido`, `es_nueva_vendedora` y `tipo` dentro de su catálogo |

Como pide el informe, el piloto se extiende a `fact_pedidos_detalle` y
`dim_producto`: cada línea de detalle pertenece a un pedido, cada producto tiene
categoría y `fuente_categoria` está en su catálogo. Que cada línea corresponda a
un producto del catálogo es advertencia (ver la tabla de abajo).

Las reglas que aún requieren confirmación de negocio no se incluyen en esta versión:
coordinadoras o líderes ausentes en `dim_vendedor` y cantidades negativas en el
detalle (devoluciones o ajustes sin confirmar).

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
| `fact_pedidos_detalle` | Cada línea corresponde a un producto del catálogo | ≈36.000 (10%, según `modelo_dimensional.md`) | Decidir cómo tratar los productos dados de baja; casi todas las líneas son antiguas |

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

## Señales para Observabilidad

El Job no envía avisos. Según el informe, Cloud Logging recoge sus registros y
Datadog centraliza las alertas ante un rechazo de calidad (frente de
Observabilidad). El Job escribe una línea JSON por evento, con `severity` para que
Cloud Logging le asigne el nivel:

| Evento | `severity` | Cuándo | Campos útiles |
| --- | --- | --- | --- |
| `quality_started` | `INFO` | Al empezar | `run_id`, `dataset`, `tables` |
| `quality_table` | `ERROR` si falló una regla crítica, `WARNING` si solo advertencias, `INFO` si pasó | Una por tabla | `table`, `critical_failures`, `warnings` (descripciones de las reglas, sin valores de los datos) |
| `quality_finished` | `ERROR` si se rechazó, `WARNING` si pasó con advertencias, `INFO` si pasó limpio | Al terminar | `success`, `warnings`, `data_docs_prefix` (carpeta del reporte) |
| `quality_error` | `ERROR` | Error técnico: no se pudo validar | `error_type`, `message` |

Filtros de Cloud Logging para las alertas (dev; en prod cambia el proyecto):

```text
# Rechazo de calidad o error técnico del Job
resource.type="cloud_run_job"
resource.labels.job_name="glamour-dataops-dev-crj-quality"
severity>=ERROR
jsonPayload.event=("quality_finished" OR "quality_error")

# Detalle por tabla de un rechazo
resource.type="cloud_run_job"
resource.labels.job_name="glamour-dataops-dev-crj-quality"
jsonPayload.event="quality_table"
severity>=ERROR
```

Cuando el Job falla, el workflow también registra el error del paso
`validar_calidad` (nivel de registro `LOG_ERRORS_ONLY`). La alerta puede enlazar el
reporte con `data_docs_prefix`, o con `reporte_calidad` en la salida del workflow
cuando la ejecución termina bien.

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
