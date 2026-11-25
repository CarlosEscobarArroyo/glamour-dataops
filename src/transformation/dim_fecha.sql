-- Calendario: un día por fila, de 2010 a 2030. Sirve para agrupar por mes,
-- trimestre o año. id_fecha es el número de día contado desde 2010-01-01
-- (1, 2, 3, ...).
CREATE OR REPLACE TABLE bq_validation.dim_fecha AS
SELECT
  DATE_DIFF(fecha, DATE '2010-01-01', DAY) + 1 AS id_fecha,
  fecha,
  EXTRACT(YEAR FROM fecha) AS anio,
  EXTRACT(MONTH FROM fecha) AS mes,
  EXTRACT(DAY FROM fecha) AS dia,
  EXTRACT(QUARTER FROM fecha) AS trimestre
FROM UNNEST(GENERATE_DATE_ARRAY(DATE '2010-01-01', DATE '2030-12-31')) AS fecha;
