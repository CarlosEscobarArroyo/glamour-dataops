-- Pedidos: una fila por pedido, sin los anulados.
-- Tiene dos fechas porque el negocio mide dos cosas distintas:
--   id_fecha       fecha en que se hizo el pedido.
--   id_fecha_pago  fecha en que se pagó; vacío si aún no se ha pagado. Las ventas
--                  que reporta el negocio son monto_pagado agrupado por esta fecha.
-- id_coordinadora e id_ubigeo son los que tiene hoy la vendedora, no los que
-- tenía cuando hizo el pedido.

-- Convierte un texto 'AAAA-MM-DD' en fecha. Devuelve NULL si no es una fecha real
-- (como '0000-00-00') o si el año es absurdo (errores de digitación del origen).
CREATE TEMP FUNCTION fecha_valida(texto STRING) AS (
  IF(
    SAFE_CAST(texto AS DATE) BETWEEN DATE '1900-01-01' AND DATE '2100-12-31',
    SAFE_CAST(texto AS DATE),
    NULL
  )
);

CREATE OR REPLACE TABLE bq_validation.fact_pedidos AS
WITH pedido AS (
  SELECT
    ccodpedido AS id_pedido,
    ccodcampana AS id_campana,
    ccodcliente AS id_vendedor,
    fecha_valida(dfecpedido) AS fecha_pedido,
    fecha_valida(dfecpago) AS fecha_pago,
    nmonpedido AS monto_total_pedido,
    nmonpago AS monto_pagado,
    -- Un pedido sin comisión es una venta directa; con comisión, por catálogo.
    IF(nmoncomision = 0, 'Directo', 'Catalogo') AS tipo
  FROM bq_staging.documento
  WHERE cestpedido != '9'  -- 9 = pedido anulado
)
SELECT
  pedido.id_pedido,
  pedido.id_campana,
  pedido.id_vendedor,
  fecha_pedido.id_fecha,
  fecha_pago.id_fecha AS id_fecha_pago,
  vendedor.id_coordinadora,
  vendedor.id_ubigeo,
  pedido.monto_total_pedido,
  pedido.monto_pagado,
  -- 1 si es el primer pedido de la vendedora (el de su fecha más antigua).
  IF(
    pedido.fecha_pedido = MIN(pedido.fecha_pedido) OVER (PARTITION BY pedido.id_vendedor),
    1,
    0
  ) AS es_nueva_vendedora,
  pedido.tipo
FROM pedido
LEFT JOIN bq_validation.dim_fecha AS fecha_pedido
  ON fecha_pedido.fecha = pedido.fecha_pedido
LEFT JOIN bq_validation.dim_fecha AS fecha_pago
  ON fecha_pago.fecha = pedido.fecha_pago
LEFT JOIN bq_validation.dim_vendedor AS vendedor
  ON vendedor.id_vendedor = pedido.id_vendedor;
