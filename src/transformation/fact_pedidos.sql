-- Pedidos: una fila por pedido, sin los anulados.
-- Sumados por campaña, los pedidos y los montos cuadran con la pantalla "Resumen de
-- Campaña" del sistema, que también desglosa por estado_pedido:
--   monto_total_pedido  Monto Catálogo
--   monto_comision      Monto Comisión
--   monto_envio         Monto Envío
--   monto_pagado        Monto Pago: lo que debe pagar la vendedora (catálogo menos
--                       comisión más envío). Tiene valor aunque aún no haya pagado.
-- Tiene dos fechas:
--   id_fecha       fecha en que se hizo el pedido.
--   id_fecha_pago  fecha en que se pagó; vacío si aún no se ha pagado. Filtrar por
--                  ella deja fuera los pedidos pendientes y ya no cuadra con el sistema.
-- id_coordinadora e id_ubigeo son los que tiene hoy la vendedora, no los que
-- tenía cuando hizo el pedido.

CREATE OR REPLACE TABLE bq_validation.fact_pedidos AS
WITH pedido AS (
  SELECT
    ccodpedido AS id_pedido,
    ccodcampana AS id_campana,
    ccodcliente AS id_vendedor,
    bq_validation.fecha_valida(dfecpedido) AS fecha_pedido,
    bq_validation.fecha_valida(dfecpago) AS fecha_pago,
    -- Nombres que muestra el sistema en "Resumen de Campaña". Los estados 3 y 6
    -- no se han visto en esa pantalla: llevan el nombre del catálogo (webparametros).
    CASE cestpedido
      WHEN '0' THEN 'Borrador'
      WHEN '1' THEN 'Emitido'
      WHEN '2' THEN 'Pago reportado'
      WHEN '3' THEN 'Por Facturar'
      WHEN '4' THEN 'Facturado'
      WHEN '5' THEN 'Despachado'
      WHEN '6' THEN 'Entregado'
      ELSE cestpedido
    END AS estado_pedido,
    nmonpedido AS monto_total_pedido,
    nmoncomision AS monto_comision,
    nmonenvio AS monto_envio,
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
  pedido.estado_pedido,
  pedido.monto_total_pedido,
  pedido.monto_comision,
  pedido.monto_envio,
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
