# Modelo dimensional de Glamour Perú

Descripción de las tablas que consumen los dashboards. Fuente: esquemas y datos
de `glamour-dataops-dev.bq_dimensional` leídos el 21/11/2026. Las reglas de
transformación no están en este repositorio, así que lo que aquí se dice sobre
filtros y definiciones está **inferido de los datos** y marcado como tal.

- **Proyecto:** `glamour-dataops-dev`
- **Dataset:** `bq_dimensional` (ubicación `US`)
- **Carga:** las tablas se reemplazan completas en cada ejecución.
- **Moneda:** soles (S/).

## Vista general

```
dim_fecha ──────┐            ┌────── dim_campana
dim_vendedor ───┼─ fact_pedidos ─┼── dim_coordinadora
dim_ubicacion ──┘       │
                        │ id_pedido
                 fact_pedidos_detalle ── dim_producto
                                              │ id_producto
fact_stock_actual ──── dim_variante ──── fact_movimientos_stock
```

| Tabla | Filas | Una fila es |
| --- | ---: | --- |
| `fact_pedidos` | 59.741 | Un pedido |
| `fact_pedidos_detalle` | 353.284 | Una línea de producto dentro de un pedido |
| `fact_stock_actual` | 19.050 | El saldo actual de una variante (producto + color + talla) |
| `fact_movimientos_stock` | 362.563 | Una entrada o salida de almacén de una variante |
| `dim_vendedor` | 21.926 | Una vendedora (asesora o líder) |
| `dim_coordinadora` | 7 | Una coordinadora |
| `dim_campana` | 176 | Una campaña comercial |
| `dim_producto` | 5.184 | Un producto del catálogo |
| `dim_variante` | 19.153 | Una combinación producto + color + talla |
| `dim_ubicacion` | 1.864 | Un ubigeo (distrito) |
| `dim_fecha` | 7.670 | Un día, del 01/01/2010 al 31/12/2030 |

## Hechos

### `fact_pedidos`

Pedidos del 02/11/2016 al presente, en cualquier estado salvo Anulado (estado 9
del origen, 21.913 pedidos). Incluye pedidos aún no pagados: 83 no tienen fecha
de pago.

Cuadra con la pantalla "Resumen de Campaña" del sistema (comprobado el
22/11/2026 con `2026 C11 PRIMAVERA VIBRANTE`: 242 pedidos, 81.568,12 de
catálogo y 61.479,55 de pago; y con `2026 C10 TENDENCIAS QUE INSPIR`: 208,
69.436,87 y 52.467,94).

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_pedido` | INT64 | Número de pedido. Clave de la tabla. |
| `id_campana` | INT64 | Campaña del pedido → `dim_campana`. |
| `id_vendedor` | INT64 | Asesora que hizo el pedido → `dim_vendedor`. |
| `id_fecha` | INT64 | Fecha del pedido → `dim_fecha`. |
| `id_fecha_pago` | INT64 | Fecha de pago → `dim_fecha`. Nulo si no se pagó. |
| `id_coordinadora` | INT64 | Coordinadora **actual** de la asesora → `dim_coordinadora`. No guarda historia. |
| `id_ubigeo` | STRING | Ubigeo de la asesora → `dim_ubicacion`. |
| `estado_pedido` | STRING | Estado con el nombre que muestra el sistema: Borrador, Emitido, Pago reportado, Por Facturar, Facturado, Despachado, Entregado. Los anulados no están en la tabla. |
| `monto_total_pedido` | NUMERIC | Importe a precio de catálogo. Es el "Monto Catálogo" del sistema. |
| `monto_comision` | NUMERIC | Comisión de la asesora. Es el "Monto Comisión" del sistema. |
| `monto_envio` | NUMERIC | Costo de envío. Es el "Monto Envío" del sistema. |
| `monto_pagado` | NUMERIC | Monto a pagar por la asesora: catálogo − comisión + envío. Es el "Monto Pago" del sistema. Tiene valor aunque el pedido aún no esté pagado. |
| `es_nueva_vendedora` | INT64 | 1 si es el primer pedido de la asesora, 0 si no. |
| `tipo` | STRING | `Catalogo` (52.685) o `Directo` (7.056). |

**Venta:** para cuadrar con el sistema se suman todos los pedidos de la tabla
por campaña, sin filtrar por fecha de pago. Filtrar por `id_fecha_pago` deja
fuera los pedidos pendientes de pago.

### `fact_pedidos_detalle`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_pedido_detalle` | INT64 | Identificador de la línea. |
| `id_pedido` | INT64 | Pedido al que pertenece → `fact_pedidos`. Todas las líneas encuentran pedido. |
| `id_campana`, `id_vendedor`, `id_fecha`, `id_ubigeo` | | Copiados del pedido, para filtrar sin unir. |
| `id_producto` | STRING | Producto → `dim_producto`. |
| `cantidad` | NUMERIC | Unidades. Hay 1.484 líneas negativas (devoluciones o ajustes, sin confirmar). |
| `importe_producto` | NUMERIC | Importe de la línea. |

Limitaciones: 36.385 líneas (10%) apuntan a productos que ya no existen en
`dim_producto`, casi todas antiguas. No trae talla ni color, ni fecha de pago
(para ventas por fecha de pago hay que unir con `fact_pedidos`).

### `fact_stock_actual`

Foto del almacén al momento de la carga. No tiene historia.

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_variante` | STRING | Variante → `dim_variante`. Clave de la tabla. |
| `id_producto` | STRING | Producto → `dim_producto`. |
| `stock` | NUMERIC | Unidades físicas. |
| `stock_retenido` | NUMERIC | Unidades reservadas. |
| `stock_disponible` | NUMERIC | Unidades que se pueden ofrecer. |
| `stock_minimo` | NUMERIC | Mínimo configurado. |
| `bajo_minimo` | INT64 | 1 si está por debajo del mínimo (247 variantes). |
| `fecha_ultimo_movimiento` | DATETIME | Último movimiento de la variante. |

6.610 variantes tienen stock; 2.808 tienen 1 o 2 unidades disponibles; 123
tienen stock negativo.

### `fact_movimientos_stock`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_movimiento` | INT64 | Identificador del movimiento. |
| `id_nota` | INT64 | Nota de almacén que lo agrupa. |
| `id_variante` | STRING | Variante → `dim_variante`. |
| `id_producto` | STRING | Producto → `dim_producto`. |
| `id_fecha` | INT64 | Fecha → `dim_fecha`. |
| `id_pedido` | INT64 | Pedido asociado, cuando es un despacho. |
| `tipo_movimiento` | STRING | `Entrada` o `Salida`. |
| `concepto` | STRING | Motivo: Despacho, Producción, Ajuste de Inventario, Cambio de talla, Compra de Mercadería, Devolución, etc. |
| `cantidad` | NUMERIC | Unidades, siempre positivas. |
| `cantidad_con_signo` | NUMERIC | Positiva en entradas, negativa en salidas. Es la que se suma. |
| `stock_resultante` | NUMERIC | Saldo después del movimiento. |

No hay precios ni costos: sirve para unidades, no para valorizar inventario.

## Dimensiones

### `dim_vendedor`

Vendedoras: 20.860 asesoras y 1.066 líderes.

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_vendedor` | INT64 | Código de la asesora. Clave. |
| `nombre_vendedor` | STRING | Nombre. |
| `sexo` | STRING | `F` o `M`. Hay 177 filas con `1` o `2` sin interpretar. |
| `fecha_nacimiento` | DATE | |
| `id_ubigeo` | STRING | → `dim_ubicacion`. |
| `celular` | STRING | Para WhatsApp. Falta en 3.107 asesoras (14%). |
| `id_lider` | INT64 | Líder de la asesora. Vacío o 0 en las líderes y en 8.581 asesoras. |
| `id_coordinadora` | INT64 | → `dim_coordinadora`. Falta en 139 asesoras. |
| `fecha_ingreso` | DATE | Fecha de inscripción. |
| `tipo_vendedor` | STRING | `Asesora` o `Líder`. |

Dato personal: `celular`, `nombre_vendedor` y `fecha_nacimiento` no deben salir
en dashboards de acceso abierto.

### `dim_coordinadora`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_coordinadora` | INT64 | Clave. |
| `nombre_coordinadora` | STRING | Solo nombre de pila: MARISOL, ELENA, YULI, NELLY, DIRECTA2, CRUZZANNY, PATRICIA. |
| `estado` | STRING | `1` activa (5), `0` inactiva (2). |
| `fecha_nacimiento` | DATE | Casi siempre vacía o de relleno. |

No tiene zona ni ubicación. `DIRECTA2` no es una persona: agrupa la venta directa.

### `dim_campana`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_campana` | INT64 | Clave. |
| `nombre_campana` | STRING | Ej. `2026 C13 NAVIDAD`. Trae año y número de campaña en el texto. |
| `estado` | STRING | `1` = campaña vigente (hoy solo una: `2026 C13 NAVIDAD`). `0` = el resto. |
| `fecha_inicio`, `fecha_fin` | DATE | Vigencia. |
| `anio` | INT64 | Año de inicio. |
| `numero_campana` | INT64 | Correlativo de 1 a 176 por fecha de inicio. **No** es el número comercial. |

Cuidado: las campañas se solapan. Un mismo número comercial tiene varias filas
(`2026 C11 PRIMAVERA VIBRANTE`, `2026 C11 LIQUIDACION`) y hay filas que no son
campañas reales (`SE DUPLICO`, `CAMBIOS Y DEVOLUCIONES`). Para "campaña
anterior" no sirve restar 1 a `numero_campana`; hay que agrupar por el `Cnn`
del nombre.

### `dim_producto`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_producto` | STRING | Clave interna (cadena larga). |
| `codigo_producto` | STRING | Código comercial, ej. `B-16560`. Es el SKU que reconoce el negocio. |
| `nombre_producto` | STRING | Ej. `BLUSA B-16560`. |
| `categoria` | STRING | Ropa (84%), Accesorios, Regalos / Incentivos, Maquillaje, Perfumes, Electrodomésticos, Hogar, Aceites Esenciales, Tecnología, Sin clasificar (194). |
| `subcategoria` | STRING | Blusas, Vestidos, Pantalones, Conjuntos, etc. |
| `fuente_categoria` | STRING | De dónde salió la categoría: `Sección del catálogo`, `Nombre del producto` (por palabras clave, menos fiable) o `Sin clasificar`. |

### `dim_variante`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_variante` | STRING | Clave: producto, color y talla unidos con `\|`. |
| `id_producto` | STRING | → `dim_producto`. |
| `nombre_producto` | STRING | `Desconocido` en 2.045 variantes sin producto en el catálogo. |
| `color` | STRING | Nombre del color, o el código (`000`) si no está en el catálogo. |
| `talla` | STRING | S, M, L, 30, STD, 500ML, etc. |

Defecto conocido: 64 variantes tienen el `id_producto` dañado en notación
científica (`1.2172821021006543e+21`) y no cruzan con `dim_producto`.

### `dim_ubicacion`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_ubigeo` | STRING | Clave (código del sistema de origen). |
| `distrito`, `provincia`, `departamento` | STRING | Vacíos en los códigos de otros países (`BO000000`, `EC000000`). |
| `ubigeo_inei` | STRING | Código INEI, útil para mapas. |

190 pedidos quedan sin departamento.

### `dim_fecha`

| Columna | Tipo | Descripción |
| --- | --- | --- |
| `id_fecha` | INT64 | Clave. |
| `fecha` | DATE | El día. Usar este campo como dimensión de fecha en los gráficos. |
| `anio`, `mes`, `dia`, `trimestre` | INT64 | Partes de la fecha. |

Se usa dos veces contra `fact_pedidos`: por `id_fecha` (fecha del pedido) y por
`id_fecha_pago` (fecha de pago).

## Lo que el modelo no tiene

- Zona de la coordinadora.
- Talla y color en las líneas de pedido.
- Historia de qué coordinadora tenía cada asesora en el pasado.
- Costos y márgenes.
- Fecha y hora de la última carga como columna.

