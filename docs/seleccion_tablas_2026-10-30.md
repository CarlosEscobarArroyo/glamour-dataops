# Selección de tablas para extracción comercial

## Decisión final aplicada

Tras revisar la propuesta, el alcance acordado es de **18 tablas**, implementadas
en `src/extraction/extract.py`. Se retiraron `webubigeo`, `webzonas`, `webzonasdet`
y `webcostos` de las 22 propuestas. `senvios` y `personaventas` tampoco forman parte
del extractor. La ubicación se resolverá con la referencia externa del legacy
(`tabla_cruzada.xlsx`), pendiente de verificar sus correcciones.

La lista final y el contrato vigente están en `src/extraction/README.md`.
El análisis que sigue conserva la propuesta inicial de 22 tablas y sus evidencias;
no representa la configuración actual del extractor.

## Propuesta inicial y evidencia

**Recomendación: 22 tablas recurrentes, 2 solo históricas y 21 fuera del pipeline
comercial.** No se propone borrar información del origen ni de la copia completa.
La selección cubre las 45 tablas sin omisiones ni solapamientos.

La revisión utiliza la copia completa del 30/10/2026 a las 18:09 de Lima:
1.170.796 filas y 626 columnas. Se profundizó en población y diversidad de campos,
actividad por año, relaciones, catálogos de códigos, cantidades y conciliaciones
aritméticas. Evidencia agregada: `seleccion_tablas_2026-10-30.json`.
El diagnóstico inicial y sus limitaciones están en `analisis_origen_2026-10-30.md`.

La lista es una decisión técnica recomendada para el alcance comercial, apoyada
en esta copia. No prueba que las tablas sin actividad reciente nunca volverán a
utilizarse. Las definiciones finales de ventas, pagos, comisiones y saldos todavía
requieren validación de negocio. No se cambió `extract.py` en esta revisión.

## Por qué conservar estas fuentes

### Pedidos, inventario y reglas

Las cinco tablas iniciales son el núcleo de pedidos, personas, productos y campañas.
El detalle siempre encuentra pedido y el pedido siempre encuentra campaña. El
inventario añade 359.853 movimientos, 93.504 notas y 18.938 variantes; todos los
movimientos encuentran nota. Hay 22.272 movimientos modificados en 2026 y 12.286
relaciones stock-campaña modificadas en 2026. Esto justifica incorporar las tablas
operativas, en lugar de inferir inventario desde ventas.

`campanarangos` contiene porcentajes y límites por campaña. Conservar esos valores
es útil para reconstruir reglas; no se afirma todavía que sean comisiones.

### Catálogos que sí aportan interpretación

`webparametros` tiene 37 grupos. El grupo de estados de pedido cubre los siete
códigos observados en pedidos. El grupo de movimientos identifica E como Entradas
y S como Salidas, cubriendo todas las notas. El concepto debe interpretarse junto
al tipo: el código 02 tiene descripciones diferentes para entradas y salidas.
Hay 226 notas cuyo concepto no coincide exactamente con el catálogo; al recortar
espacios quedan 167. No completar esas etiquetas con supuestos.

El catálogo de colores cubre 277 de los 280 códigos no vacíos observados en stock;
el de tallas cubre 58 de 59. No unir solo por valor: la clave del diccionario
incluye grupo y tipo. Los grupos de usuarios y vendedoras tampoco deben combinarse
sin interpretar su dominio: una coincidencia numérica no confirma el rol comercial.

`pagepagos` explica los códigos de pago de 59.861 pedidos. Los 21.224 restantes
tienen código cero. Es una configuración de medios de pago, no un libro de pagos.
Conservar identificador, descripción, tipo, moneda y estado; los números y titulares
de cuentas no son necesarios para clasificar ventas por medio de pago.

`seccion` y `seccioncontenido` clasifican 2.256 de los 5.148 productos existentes
(43,8%). Hay 24 códigos de producto asociados a varias secciones. La clasificación
incluye secciones editoriales además de categorías de ropa. Mantenerla como una
relación muchos-a-muchos y no como una categoría única obligatoria.

`webmodulos` permite distinguir Contenidos, Catalogo y Formularios. Todos los
registros de `contenido` tienen módulo válido. No asumir que toda esa tabla
representa mercancía vendible.

### Facturación, saldos, geografía y envío

En las 7.094 filas de `sventas`, base más IGV coincide exactamente con el total.
Son 7.086 pedidos distintos; ocho pedidos tienen más de una fila de facturación.
Hay solo 140 documentos fechados en 2026 frente a 4.514 pedidos del mismo año:
las tablas no representan la misma población y no se debe sustituir pedidos por
facturas ni multiplicar importes mediante joins uno-a-muchos.

`personasaldos` tiene 258 registros fechados en 2026. Las 5.614 filas encuentran
persona, pero 5.305 no informan pedido. Modelar el hecho por persona/operación;
no exigir un vínculo al pedido para conservarlo.

`webubigeo` encuentra correspondencia en 21.895 personas; 12 tienen código vacío
y una no coincide. Las cuatro zonas están referenciadas por 1.860 ubigeos; 354
tienen zona cero. `webzonasdet` tiene solo dos relaciones válidas, por lo que no
es un mapa geográfico completo. Se conserva junto al mapa principal para no
perder esa configuración adicional sin conocer su regla de prioridad.

Las 11 filas de `webcostos` tienen zonas válidas y tipos de envío presentes en los
pedidos. Sirven como configuración de tarifas, pero no contienen vigencia temporal:
no recalcular el costo de pedidos antiguos usando las tarifas actuales.

Las 23.199 referencias de `documentofile` encuentran pedido. Se conservan como
metadatos documentales; un archivo asociado no demuestra pago, entrega ni validez
del documento. Esta extracción no descarga los adjuntos.

## Por qué retirar otras tablas de la extracción recurrente

- `personaventas` tiene 451 filas correspondientes únicamente a la campaña 18102,
  con fechas 2018-02-01 a 2018-03-24. La combinación persona/campaña es única en
  la copia, pero dos personas no encuentran maestro. Es un resumen histórico
  aislado; no sustituye el cálculo desde pedidos actuales.
- `senvios` contiene solo 448 registros de abril–mayo de 2019. No proporciona
  información de entregas de 2026.
- `contenidodetalle` tiene 5.140 filas, pero ninguna aporta texto visible en
  `cdetcontenido` después de retirar HTML y espacios. Los demás campos descriptivos
  están vacíos. No es una fuente de atributos de producto en esta copia.
- `personapage` tiene 21.909 filas con `ccodperfil` siempre vacío y `cdefperfil`
  constante. No añade una dimensión de perfiles al análisis comercial.
- `spagos` y `personabuzon` tienen cero filas. Se excluyen del flujo actual y se
  revisan si empiezan a poblarse.
- Las tablas de portada, menús, estilos, fuentes, galerías y opciones de interfaz
  describen la configuración del sitio. No aportan hechos comerciales al alcance
  actual. Se conservan en la copia exploratoria, no como fuentes analíticas diarias.

## Problemas que no se resuelven descartando tablas

- 41.396 líneas de pedido hacen referencia a 439 códigos de producto ausentes.
  Ninguna coincidencia se recupera recortando espacios y pasando a minúsculas.
  El problema se concentra en años antiguos, pero incluye tres líneas de 2025
  y dos de 2026. No se ha demostrado que la causa sea eliminación de productos.
- 507 pedidos no tienen líneas. En 77.302 de los 80.578 pedidos con detalle,
  la suma de `nimporte` coincide exactamente con `nmonpedido`; en 3.276 no.
  No se aplicaron filtros de estado ni reglas de descuentos/envíos. Es una
  diferencia aritmética a investigar, no una declaración de ventas erróneas.
- Las cantidades del detalle son convertibles a decimal, pero hay 1.487 negativas
  y 152 ceros. No filtrarlas sin determinar cómo se representan devoluciones y ajustes.
- Hay 299.519 fechas cero. Preservarlas en llegada y aplicar reglas explícitas de
  conversión en la capa analítica; el extractor actual aún requiere ese ajuste.
- `stockmovi.nprecio` es cero en todas sus filas y solo 62 productos tienen precio
  de compra distinto de cero. La extracción permite analizar unidades y movimientos,
  pero no demuestra que exista una base para margen o valoración histórica.

## Aplicación recomendada

Usar una lista explícita de las 22 tablas recurrentes, conservando todas las filas
y los estados. Los catálogos pequeños pueden viajar en el mismo proceso diario
para mantener su versión junto a las operaciones. Una tabla fuera de esta lista
debe poder detectarse en el inventario y revisarse, sin publicarse automáticamente.

Guardar una copia histórica de `senvios` y `personaventas`. La copia exploratoria
actual reside en `/tmp`, por lo que no equivale a un archivo permanente: antes de
limpiarla o dar por cerrado el respaldo, persistirla en el destino acordado.

Excluir campos de contraseña y autenticación del flujo analítico de `persona`,
y minimizar cuentas bancarias y textos libres según los usos definidos. No se
eliminó ninguna columna ni archivo en esta revisión.

Revisar los excluidos cuando cambie el esquema, comiencen a poblarse tablas vacías
o se incorpore un caso de uso de sitio web, atención o logística. Una única copia
permite observar contenido y fechas, no confirmar la frecuencia real de actualización.

La selección recurrente contiene 1.142.349 filas de esta copia (97,6% del total).
Su finalidad es definir el alcance y evitar datos sin uso, no prometer una gran
reducción de volumen. La copia completa ocupa aproximadamente 27 MB en Parquet.

## Decisión por tabla

### Extracción recurrente: 22 tablas

| Tabla | Filas | Motivo |
| --- | ---: | --- |
| `persona` | 21,908 | Maestro de personas: 21.908 filas. Conservar relaciones comerciales y ubicación; excluir autenticación del flujo analítico. |
| `contenido` | 5,148 | Catálogo de 5.148 registros. Necesario para productos; no cubre todas las referencias históricas. Conservar ccodmodulo. |
| `campana` | 174 | 174 campañas; todos los pedidos encuentran campaña. Validar fechas anómalas sin corregir el origen. |
| `documento` | 81,085 | 81.085 pedidos de 2016–2026. Conservar estados, importes, pagos, devoluciones y fechas. |
| `documentodetalle` | 424,953 | 424.953 líneas, todas con pedido. Incluye talla, color, cantidades y precios. Preservar referencias sin producto. |
| `stockcontrol` | 18,938 | 18.938 variantes; 6.752 tienen stock distinto de cero. Fuente del estado actual, no del costo histórico. |
| `stockmovi` | 359,853 | 359.853 movimientos, 22.272 modificados en 2026; todos encuentran nota. nprecio siempre cero. |
| `stocknotas` | 93,504 | 93.504 cabeceras; tipos E/S coinciden con Entradas/Salidas en el catálogo. Interpretar concepto junto al tipo. |
| `contenidoprenda` | 94,804 | 94.804 relaciones stock-campaña; ambas referencias tienen coincidencia completa. 12.286 modificaciones en 2026. |
| `campanarangos` | 560 | 560 rangos y porcentajes, todos con campaña. Conservar reglas originales; validar su finalidad comercial. |
| `sventas` | 7,094 | 7.094 documentos, 140 fechados en 2026. Todos encuentran pedido y base + IGV = total en todas las filas; cobertura parcial de pedidos. |
| `personasaldos` | 5,614 | 5.614 movimientos, 258 fechados en 2026; todos con persona. 5.305 no tienen pedido informado. |
| `webubigeo` | 2,214 | 2.214 ubicaciones; 21.895 personas encuentran código. 12 códigos vacíos y uno sin coincidencia. |
| `webzonas` | 4 | 4 zonas nombradas; 1.860 ubigeos las referencian y 354 tienen zona cero. |
| `webzonasdet` | 2 | 2 relaciones válidas de zona/ubigeo. Conservar para investigar su función complementaria; no sustituir el mapa principal con ellas. |
| `webcostos` | 11 | 11 tarifas por zona, rango de monto y tipo de envío. Todas las zonas existen y tipos 11/12/13 aparecen en pedidos; no hay vigencia temporal. |
| `webparametros` | 931 | 931 registros y 37 grupos; incluye etiquetas de pedidos, tallas, colores y movimientos. La clave requiere grupo/tipo/valor. |
| `seccion` | 55 | 55 secciones con nombres comerciales y editoriales. Conservar para aprovechar la clasificación explícita del catálogo. |
| `seccioncontenido` | 2,286 | 2.286 relaciones válidas con secciones; 2.256 productos existentes clasificados (43,8% del catálogo), 24 códigos en varias secciones. |
| `pagepagos` | 9 | 9 medios/configuraciones de pago referenciados por 59.861 pedidos; los 21.224 restantes tienen código cero. No contiene transacciones. |
| `webmodulos` | 3 | 3 módulos: Contenidos, Catalogo y Formularios. Los 5.148 registros de contenido encuentran módulo; permite separar dominios. |
| `documentofile` | 23,199 | 23.199 referencias a archivos, todas con pedido. Conservar metadatos para trazabilidad documental; no acredita pago ni descarga adjuntos. |

### Solo histórico: 2 tablas

| Tabla | Filas | Motivo |
| --- | ---: | --- |
| `senvios` | 448 | 448 registros con fechas únicamente de abril–mayo de 2019. Conservar una copia histórica; no usar como fuente de entregas actuales. |
| `personaventas` | 451 | 451 filas de una sola campaña, del 2018-02-01 al 2018-03-24. Sin duplicados persona-campaña en esta copia; dos personas no existen. Resumen antiguo, no fuente vigente. |

### Excluir del pipeline comercial: 21 tablas

| Tabla | Filas | Motivo |
| --- | ---: | --- |
| `contenidodetalle` | 5,140 | 5.140 filas; campos descriptivos vacíos. cdetcontenido no conserva texto visible al quitar HTML/espacios. No añade atributos comerciales en esta copia. |
| `contenidogaleria` | 115 | 115 registros de imágenes/textos de galería, todos modificados en 2016. Fuera del análisis comercial actual; conservar en la copia exploratoria. |
| `documentotmp` | 3 | 3 líneas de trabajo temporal con usuario, producto y cantidad. No tratarlas como pedidos confirmados. |
| `page` | 1 | 1 registro de configuración del sitio: empresa, redes, presentación y opciones. No es una tabla de operaciones comerciales. |
| `pagedocs` | 8 | 8 configuraciones de tipos/series/correlativos. Los documentos emitidos se obtienen de sventas/documento; no tratar correlativos como ventas. |
| `pagehome` | 33 | 33 bloques de portada con diseño, enlaces, imágenes y opciones. |
| `pagehomedet` | 138 | 138 asociaciones de bloques de portada y destinos. |
| `pagehomeitem` | 8 | 8 elementos visuales de portada. |
| `pagehomesub` | 10 | 10 subelementos con efectos, transformaciones y animaciones. |
| `pagemenu` | 2 | 2 configuraciones de menú. |
| `personabuzon` | 0 | 0 filas en la extracción; revisar si comienza a poblarse. |
| `personapage` | 21,909 | 21.909 asociaciones al sitio; ccodperfil vacío en todas y cdefperfil constante. No aporta segmentación comercial en esta copia. |
| `secciondetalle` | 55 | 55 filas de contenido editorial adicional: solo 4 textos poblados; campos empresariales vacíos. La clasificación está en seccion/seccioncontenido. |
| `seccionmenu` | 8 | 8 relaciones de navegación entre secciones y menús. |
| `spagos` | 0 | 0 filas. No es fuente disponible de pagos; los datos actuales están en documento y sus catálogos. |
| `wsestilo` | 1 | 1 configuración de estilos visuales con 69 columnas. |
| `wsestiloclases` | 32 | 32 clases de presentación. |
| `wsestilocontenido` | 12 | 12 configuraciones de presentación de contenido. |
| `wsestilofuentes` | 11 | 11 fuentes de presentación. |
| `wsestiloseccion` | 11 | 11 estilos de secciones. |
| `wsopciones` | 51 | 51 opciones/rutas/permisos del sistema; no son eventos de actividad ni transacciones. |
