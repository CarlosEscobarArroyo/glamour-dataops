-- Variantes: una fila por producto + color + talla. Es el nivel al que el negocio
-- controla el stock.
--
-- Incluye las variantes del control de stock y también las que solo aparecen en
-- movimientos (variantes que ya no están en el control), para que ningún
-- movimiento se quede sin variante.
-- id_variante es el texto 'producto|color|talla', porque el origen solo numera
-- las variantes que están en el control de stock.
-- Algunas variantes apuntan a productos que ya no existen en el catálogo: se
-- conservan con nombre_producto 'Desconocido'.
CREATE OR REPLACE TABLE bq_validation.dim_variante AS
WITH variante AS (
  SELECT ccodcontenido, ccodcolor, ccodtalla FROM bq_staging.stockcontrol
  UNION DISTINCT
  SELECT ccodcontenido, ccodcolor, ccodtalla FROM bq_staging.stockmovi
),
etiqueta AS (
  -- Nombres de tallas (grupo 0028) y colores (grupo 0029) del catálogo de
  -- parámetros. El tipo 1 son los valores; el tipo 0 es el título del grupo.
  SELECT
    ccodparametro AS grupo,
    TRIM(cvalparametro) AS codigo,
    TRIM(cnombrees) AS nombre
  FROM bq_staging.webparametros
  WHERE ccodparametro IN ('0028', '0029') AND ctipparametro = '1'
)
SELECT
  CONCAT(variante.ccodcontenido, '|', variante.ccodcolor, '|', variante.ccodtalla) AS id_variante,
  variante.ccodcontenido AS id_producto,
  IFNULL(producto.nombre_producto, 'Desconocido') AS nombre_producto,
  -- Si el código no está en el catálogo se muestra el código, sin inventar un nombre.
  COALESCE(NULLIF(color.nombre, ''), NULLIF(variante.ccodcolor, ''), 'Sin color') AS color,
  COALESCE(NULLIF(talla.nombre, ''), NULLIF(variante.ccodtalla, ''), 'Sin talla') AS talla
FROM variante
LEFT JOIN bq_validation.dim_producto AS producto
  ON producto.id_producto = variante.ccodcontenido
LEFT JOIN etiqueta AS color
  ON color.grupo = '0029' AND color.codigo = variante.ccodcolor
LEFT JOIN etiqueta AS talla
  ON talla.grupo = '0028' AND talla.codigo = variante.ccodtalla;
