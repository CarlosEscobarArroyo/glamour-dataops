-- Detalle de pedidos: una fila por producto dentro de un pedido. Solo incluye los
-- pedidos que están en fact_pedidos (es decir, sin los anulados), y repite sus
-- claves para poder agrupar el detalle sin cruzar con el pedido.
CREATE OR REPLACE TABLE bq_validation.fact_pedidos_detalle AS
SELECT
  pedido.id_pedido,
  pedido.id_campana,
  pedido.id_vendedor,
  pedido.id_fecha,
  pedido.id_ubigeo,
  detalle.idpedido AS id_pedido_detalle,
  detalle.ccodcontenido AS id_producto,
  SAFE_CAST(detalle.ncantidad AS NUMERIC) AS cantidad,
  detalle.nimporte AS importe_producto
FROM bq_staging.documentodetalle AS detalle
JOIN bq_validation.fact_pedidos AS pedido
  ON pedido.id_pedido = detalle.ccodpedido;
