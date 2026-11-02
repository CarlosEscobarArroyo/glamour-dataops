# Primera extracción exploratoria del origen

Extracción finalizada el 2026-10-30 a las 23:09:49 UTC (18:09:49 en Lima).
Se leyeron las 45 tablas base visibles: **1.170.796 filas y 626 columnas**.
No se encontraron vistas visibles. Los Parquet ocupan 27.006.663 bytes.
Estos conteos corresponden a los archivos leídos, no a estimaciones de
`information_schema.TABLES`.

## Evidencia y alcance

- Copia local temporal: `/tmp/glamour-discovery/20261030T230910Z/`.
- `data/manifest.json`: lista de tablas, archivos y filas extraídas.
- `schema.json`: columnas y restricciones declaradas en el origen.
- `profile.json`: nulos y cadenas vacías por columna.
- `analysis.json`: fechas, claves, campos monetarios y relaciones comprobadas.
- Scripts exploratorios: `/tmp/glamour-discovery/run.py` y `analyze.py`.
- Resumen agregado persistido junto a este documento: `analisis_origen_2026-10-30.json`.

La lectura fue secuencial, sin una instantánea transaccional común. Las
relaciones se comprobaron sobre esa copia; diferencias concurrentes son posibles.
Se compararon claves como cadenas exactas, sin recortar espacios, cambiar
mayúsculas ni replicar la colación SQL. Una falta de coincidencia no demuestra
por sí sola un error de negocio. No se descargaron archivos externos apuntados
por URLs. No se modificaron datos del origen.

La cuenta personal autenticada permitió leer los cuatro secretos existentes.
Se comprobó la conexión con el puerto 3306; `MYSQL_PORT` no estuvo disponible.
Las credenciales ADC utilizadas por el extractor regular corresponden a otra
configuración y no tienen acceso a esos secretos. El bucket configurado devuelve
404; por ello esta extracción es local, no una ejecución publicada en GCS.

## Hallazgos comprobados

1. **El extractor actual falla con los datos reales de fechas.** El primer
   intento terminó con `ArrowTypeError` en `campana`. La copia exploratoria
   completó la lectura conservando DATE/DATETIME/TIMESTAMP/TIME como texto SQL
   en un adaptador temporal. Se encontraron 299.519 fechas cero en 15 columnas.
   No se convirtieron silenciosamente a nulos. Los decimales y demás tipos
   conservaron el mapeo del extractor. El código de producción todavía requiere
   resolver el tratamiento de fechas cero.
2. **Pedidos y detalle tienen cobertura histórica real.** `documento` contiene
   81.085 filas con fechas de pedido entre 2016-11-02 y 2026-10-30.
   Las 424.953 filas de `documentodetalle` encuentran su pedido. Todos los pedidos
   encuentran campaña; 96 no encuentran persona por la clave comparada.
3. **El catálogo actual no cubre todas las referencias históricas.** 41.396
   líneas de pedido, 1.968 filas de stock y 31.272 movimientos no encuentran una
   coincidencia exacta en `contenido`. No eliminar esas filas mediante INNER JOIN.
   Falta investigar bajas, códigos históricos y reglas de comparación.
4. **Hay información operativa de inventario actualizada.** `stockmovi` contiene
   359.853 filas y `stocknotas` 93.504, con fechas hasta 2026-10-30. Todos los
   movimientos encuentran nota. Las 94.804 filas de `contenidoprenda` encuentran
   stock y campaña. Esto valida la posibilidad técnica de esas relaciones,
   no el significado de los estados y signos de las operaciones.
5. **No hay base suficiente para prometer margen histórico.** `stockmovi.nprecio`
   es cero en sus 359.853 filas. `contenido.nprecompra` solo tiene 62 valores
   distintos de cero entre 5.148 productos. No está validada una fuente de costo
   histórico por operación.
6. **Facturación y saldos sí tienen registros hasta 2026-10-30.** `sventas`
   contiene 7.094 filas, todas con pedido correspondiente. `personasaldos`
   contiene 5.614 filas, todas con persona correspondiente; 5.305 tienen vacío
   el pedido. No asumir que todo saldo se puede asignar a un pedido.
7. **Dos tablas están realmente vacías:** `spagos` y `personabuzon`.
   Los 448 registros de `senvios` tienen fechas entre 2019-04-05 y 2019-05-31.
   No hay evidencia en esa tabla de logística posterior a mayo de 2019.
8. **Los campos que descartaba el legacy tienen contenido medible.** En pedidos,
   67.811 filas tienen comisión distinta de cero, 56.363 tienen envío distinto
   de cero, 604 tienen importe devuelto distinto de cero y 4.525 tienen saldo
   de pago distinto de cero. `nporpago` es cero en toda la tabla. En detalle,
   8.692 filas tienen `nprepromo` distinto de cero. Su significado debe confirmarse.
9. **No hay claves foráneas declaradas en el esquema visible.** No aparecieron
   duplicados en las claves primarias declaradas. `personaventas` no presenta
   clave primaria declarada en este esquema, a diferencia de lo que sugería el
   inventario previo. No extrapolar la unicidad a todas sus combinaciones.
10. **Fechas válidas sintácticamente también necesitan reglas de negocio.**
    `campana.dfecinicio` llega al año 1019 y `dfecfinal` al 9999.
    `documento.dfecfactura` comienza en 1988. No corregirlas automáticamente.

## Propuesta de alcance a partir de la evidencia

Esta es una recomendación técnica para discutir, no una validación de reglas
comerciales ni una lista aplicada automáticamente al extractor.

- Mantener las cinco tablas actuales, conservando estados, anulaciones,
  devoluciones, tallas, colores y campos monetarios para su análisis posterior.
- Incorporar inicialmente `stockcontrol`, `stockmovi`, `stocknotas`,
  `contenidoprenda`, `campanarangos`, `sventas`, `personasaldos` y `webubigeo`:
  tienen datos y relaciones comprobables. Preservar las referencias sin
  correspondencia para investigar, en lugar de filtrarlas al extraer.
- Evaluar los catálogos `webparametros`, `webzonas`, `webzonasdet`, `seccion`,
  `seccioncontenido`, `contenidodetalle` y `personapage` antes de usarlos para
  asignar significado a códigos. La presencia de registros no valida su función.
- Conservar `senvios` como histórico si se necesita; no usarlo como fuente
  actual de entregas. `personaventas` requiere reconciliación con el detalle.
- `documentofile` contiene referencias, no el contenido de los documentos.
  Sus 23.199 registros encuentran pedido, pero no se verificaron los archivos.
- Las tablas de presentación web y las temporales quedan en la copia exploratoria.
  Su incorporación diaria necesita un propósito concreto; no descartarlas del
  respaldo por el mero nombre.
- Revisar campos de autenticación de `persona` antes de publicar una extracción
  recurrente. La copia exploratoria incluye todas las columnas solicitadas y
  permanece fuera de Git, con permisos locales restringidos. El informe no
  publica credenciales, identificadores personales ni valores de contacto.

## Decisiones para extract.py

1. Resolver el tratamiento de fechas cero preservando el valor original en la
   capa de llegada y convirtiendo/validando posteriormente en la capa analítica.
   La adaptación de texto utilizada en esta exploración no fue aplicada aún al
   extractor de producción.
2. Definir una lista explícita de tablas y exclusiones de columnas después de
   revisar este informe. El descubrimiento de todas las tablas sirve para esta
   exploración; no equivale a una decisión de publicar todo diariamente.
3. Conservar el inventario del esquema junto al manifiesto para detectar cambios.
4. Decidir si se requiere una instantánea consistente entre tablas. La extracción
   actual no la garantiza.
5. No implementar incrementales solo por encontrar `dfecmodifica`: falta comprobar
   que cubre todas las modificaciones y definir el manejo de eliminaciones.
6. Para ejecutar en GCS: crear/verificar el bucket, configurar acceso con la cuenta
   correcta y crear el secreto `MYSQL_PORT` con el puerto comprobado 3306.

## Inventario de filas extraídas

Los siguientes conteos provienen del manifiesto de la copia completada.

| Tabla | Filas | Columnas |
| --- | ---: | ---: |
| `campana` | 174 | 9 |
| `campanarangos` | 560 | 6 |
| `contenido` | 5,148 | 41 |
| `contenidodetalle` | 5,140 | 9 |
| `contenidogaleria` | 115 | 9 |
| `contenidoprenda` | 94,804 | 6 |
| `documento` | 81,085 | 37 |
| `documentodetalle` | 424,953 | 15 |
| `documentofile` | 23,199 | 3 |
| `documentotmp` | 3 | 6 |
| `page` | 1 | 43 |
| `pagedocs` | 8 | 7 |
| `pagehome` | 33 | 37 |
| `pagehomedet` | 138 | 2 |
| `pagehomeitem` | 8 | 8 |
| `pagehomesub` | 10 | 39 |
| `pagemenu` | 2 | 7 |
| `pagepagos` | 9 | 12 |
| `persona` | 21,908 | 39 |
| `personabuzon` | 0 | 12 |
| `personapage` | 21,909 | 4 |
| `personasaldos` | 5,614 | 9 |
| `personaventas` | 451 | 6 |
| `seccion` | 55 | 35 |
| `seccioncontenido` | 2,286 | 5 |
| `secciondetalle` | 55 | 9 |
| `seccionmenu` | 8 | 4 |
| `senvios` | 448 | 14 |
| `spagos` | 0 | 11 |
| `stockcontrol` | 18,938 | 9 |
| `stockmovi` | 359,853 | 11 |
| `stocknotas` | 93,504 | 14 |
| `sventas` | 7,094 | 17 |
| `webcostos` | 11 | 6 |
| `webmodulos` | 3 | 3 |
| `webparametros` | 931 | 12 |
| `webubigeo` | 2,214 | 5 |
| `webzonas` | 4 | 5 |
| `webzonasdet` | 2 | 2 |
| `wsestilo` | 1 | 69 |
| `wsestiloclases` | 32 | 3 |
| `wsestilocontenido` | 12 | 6 |
| `wsestilofuentes` | 11 | 5 |
| `wsestiloseccion` | 11 | 6 |
| `wsopciones` | 51 | 9 |

## Relaciones comprobadas

Comparación exacta de claves convertidas a texto. Los ceros se informan por separado; no se presupone que sean errores.

| Referencia | Destino | Vacíos/nulos | Ceros | Sin coincidencia, excluyendo cero |
| --- | --- | ---: | ---: | ---: |
| `documentodetalle.ccodpedido` | `documento.ccodpedido` | 0 | 0 | 0 |
| `documentodetalle.ccodcontenido` | `contenido.ccodcontenido` | 0 | 0 | 41396 |
| `documento.ccodcliente` | `persona.ccodpersona` | 0 | 0 | 96 |
| `documento.ccodcampana` | `campana.ccodcampana` | 0 | 0 | 0 |
| `stockcontrol.ccodcontenido` | `contenido.ccodcontenido` | 0 | 0 | 1968 |
| `stockmovi.ccodnota` | `stocknotas.ccodnota` | 0 | 0 | 0 |
| `stockmovi.ccodcontenido` | `contenido.ccodcontenido` | 0 | 0 | 31272 |
| `stocknotas.ccodpedido` | `documento.ccodpedido` | 0 | 45771 | 9 |
| `contenidoprenda.ccodstock` | `stockcontrol.ccodstock` | 0 | 0 | 0 |
| `contenidoprenda.ccodcampana` | `campana.ccodcampana` | 0 | 0 | 0 |
| `campanarangos.ccodcampana` | `campana.ccodcampana` | 0 | 0 | 0 |
| `sventas.ccodpedido` | `documento.ccodpedido` | 0 | 0 | 0 |
| `personasaldos.ccodpersona` | `persona.ccodpersona` | 0 | 0 | 0 |
| `personasaldos.ccodpedido` | `documento.ccodpedido` | 5305 | 0 | 0 |
| `personaventas.ccodpersona` | `persona.ccodpersona` | 0 | 0 | 2 |
| `personaventas.ccodcampana` | `campana.ccodcampana` | 0 | 0 | 0 |
| `persona.ccodubigeo` | `webubigeo.ccodubigeo` | 12 | 0 | 1 |
| `documentofile.ccodpedido` | `documento.ccodpedido` | 0 | 0 | 0 |
| `seccioncontenido.ccodcontenido` | `contenido.ccodcontenido` | 0 | 0 | 6 |
