-- Movimientos de stock: una fila por variante dentro de una nota de almacén
-- (entrada o salida). La fecha, el tipo, el concepto y el pedido son los de la nota.
--   cantidad            unidades movidas, siempre en positivo.
--   cantidad_con_signo  positiva en entradas y negativa en salidas; al sumarla se
--                       obtiene la variación neta del stock.
--   stock_resultante    stock de la variante después del movimiento, según el
--                       origen. No se suma: es un saldo.
--   id_pedido           pedido que originó la nota (casi todos los despachos);
--                       vacío si la nota no viene de un pedido. Puede ser un
--                       pedido anulado, que no está en fact_pedidos.
-- Son solo unidades: el precio del movimiento está en cero en todo el origen.
CREATE OR REPLACE TABLE bq_validation.fact_movimientos_stock AS
WITH concepto AS (
  -- El mismo código de concepto significa cosas distintas en entradas (grupo
  -- 0015) y en salidas (grupo 0016), así que se busca junto con el tipo.
  SELECT
    IF(ccodparametro = '0015', 'E', 'S') AS tipo,
    TRIM(cvalparametro) AS codigo,
    TRIM(cnombrees) AS nombre
  FROM bq_staging.webparametros
  WHERE ccodparametro IN ('0015', '0016') AND ctipparametro = '1'
)
SELECT
  movimiento.ccodmovi AS id_movimiento,
  movimiento.ccodnota AS id_nota,
  CONCAT(movimiento.ccodcontenido, '|', movimiento.ccodcolor, '|', movimiento.ccodtalla) AS id_variante,
  movimiento.ccodcontenido AS id_producto,
  fecha.id_fecha,
  NULLIF(nota.ccodpedido, 0) AS id_pedido,
  IF(nota.ctipnota = 'E', 'Entrada', 'Salida') AS tipo_movimiento,
  -- Si el código no está en el catálogo se muestra el código, sin inventar un nombre.
  IFNULL(concepto.nombre, TRIM(nota.cconnota)) AS concepto,
  SAFE_CAST(movimiento.ncantidad AS NUMERIC) AS cantidad,
  IF(nota.ctipnota = 'E', 1, -1) * SAFE_CAST(movimiento.ncantidad AS NUMERIC) AS cantidad_con_signo,
  movimiento.nstock AS stock_resultante
FROM bq_staging.stockmovi AS movimiento
JOIN bq_staging.stocknotas AS nota
  ON nota.ccodnota = movimiento.ccodnota
LEFT JOIN bq_validation.dim_fecha AS fecha
  ON fecha.fecha = bq_validation.fecha_valida(nota.dfecnota)
LEFT JOIN concepto
  ON concepto.tipo = nota.ctipnota AND concepto.codigo = TRIM(nota.cconnota);
