# Calidad de datos con Great Expectations

Cloud Run Job que valida el modelo recién construido en `bq_validation`. La
activación en Cloud Workflows se hará después de calibrar las reglas manualmente
en dev. Cuando se active, un rechazo impedirá copiar el modelo candidato a
`bq_dimensional`, que conservará su última versión aprobada.

## Alcance

Las once tablas del modelo tienen un contrato estructural: tabla no vacía,
columnas exactas, clave no nula y clave única. El piloto añade reglas de negocio
para `dim_fecha`, `dim_campana`, `dim_ubicacion`, `dim_vendedor` y
`fact_pedidos`. `dim_fecha` completa el piloto descrito en el informe porque es
una dependencia directa de las fechas del hecho de pedidos.

Las reglas que aún requieren confirmación de negocio no bloquean esta versión:
montos negativos, ubicaciones opcionales, coordinadoras o líderes ausentes y
relaciones de productos históricos. Se incorporarán después de medirlas en dev.

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
evitar que los reportes expongan datos personales.

## Pruebas

Las pruebas son unitarias y no acceden a BigQuery ni Cloud Storage:

```bash
python -m pip install -r src/quality/requirements.txt
python -B -m unittest discover -s tests/quality -v
```

Después del despliegue se debe ejecutar el Job manualmente en dev y calibrar las
reglas con datos reales antes de conectarlo al pipeline diario.

## Agregar una tabla o regla

1. Agregar el contrato a `TABLE_CONTRACTS` en `suites.py`.
2. Si necesita reglas profundas, crear su función y registrarla en
   `PILOT_BUILDERS`.
3. Agregar o ajustar las pruebas.
4. Validar primero en dev. Una expectativa demasiado estricta detendría la
   publicación diaria una vez activada la compuerta.
