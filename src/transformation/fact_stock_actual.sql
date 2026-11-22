-- Stock actual: una fila por variante (producto + color + talla) con las unidades
-- que hay hoy. Es una foto del momento de la extracción: no guarda historia, cada
-- día se reemplaza. Para ver cómo cambió el stock, usar fact_movimientos_stock.
-- Son solo unidades: el origen no tiene costos para valorizar el stock.
CREATE OR REPLACE TABLE bq_validation.fact_stock_actual AS
SELECT
  CONCAT(ccodcontenido, '|', ccodcolor, '|', ccodtalla) AS id_variante,
  ccodcontenido AS id_producto,
  nstock AS stock,
  nstockrete AS stock_retenido,
  -- Lo que se puede vender: el stock real menos el retenido, igual que en el sistema.
  nstock - nstockrete AS stock_disponible,
  nstockmin AS stock_minimo,
  -- 1 si la variante tiene un mínimo definido y su stock está por debajo.
  IF(nstockmin > 0 AND nstock < nstockmin, 1, 0) AS bajo_minimo,
  -- Fecha y hora del último cambio de stock de la variante.
  SAFE_CAST(dfecmodifica AS DATETIME) AS fecha_ultimo_movimiento
FROM bq_staging.stockcontrol;
