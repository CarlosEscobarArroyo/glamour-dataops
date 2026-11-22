-- Campañas comerciales. numero_campana las numera por fecha de inicio.

-- Convierte un texto 'AAAA-MM-DD' en fecha. Devuelve NULL si no es una fecha real
-- (como '0000-00-00') o si el año es absurdo (errores de digitación del origen).
CREATE TEMP FUNCTION fecha_valida(texto STRING) AS (
  IF(
    SAFE_CAST(texto AS DATE) BETWEEN DATE '1900-01-01' AND DATE '2100-12-31',
    SAFE_CAST(texto AS DATE),
    NULL
  )
);

CREATE OR REPLACE TABLE bq_validation.dim_campana AS
WITH corregida AS (
  -- Fechas mal digitadas en el origen (años como 1019 o 9999), corregidas a mano.
  -- Se identifica cada campaña por su código, que no cambia aunque la renombren.
  SELECT
    ccodcampana,
    cnomcampana,
    cestcampana,
    CASE ccodcampana
      WHEN 19201 THEN '2019-01-05'  -- 2019 Liquidacion 01
      ELSE dfecinicio
    END AS dfecinicio,
    CASE ccodcampana
      WHEN 17106 THEN '2017-10-09'  -- Glamour 2017-08
      WHEN 19301 THEN '2019-03-25'  -- ROMA 2019-01
      WHEN 19113 THEN '2020-01-30'  -- CAMBIOS Y DEVOLUCIONES
      WHEN 23112 THEN '2023-09-11'  -- ESENZA C1 PERFUMES DEL MUNDO
      WHEN 19111 THEN '2019-12-19'  -- 2019 C 09 LIQUIDACIÓN TIENDA
      ELSE dfecfinal
    END AS dfecfinal
  FROM bq_staging.campana
),
con_fechas AS (
  SELECT
    ccodcampana AS id_campana,
    cnomcampana AS nombre_campana,
    cestcampana AS estado,
    fecha_valida(dfecinicio) AS fecha_inicio,
    fecha_valida(dfecfinal) AS fecha_fin
  FROM corregida
)
SELECT
  id_campana,
  nombre_campana,
  estado,
  fecha_inicio,
  fecha_fin,
  EXTRACT(YEAR FROM fecha_inicio) AS anio,
  ROW_NUMBER() OVER (ORDER BY fecha_inicio NULLS LAST, id_campana) AS numero_campana
FROM con_fechas;
