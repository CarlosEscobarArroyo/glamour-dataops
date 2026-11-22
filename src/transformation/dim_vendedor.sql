-- Vendedoras: las personas de nivel 2 (asesoras) y nivel 3 (líderes).
-- id_lider es la líder de una asesora; queda vacío en las líderes y en las
-- asesoras que no tienen una asignada.
-- id_coordinadora queda vacío cuando la vendedora no tiene una coordinadora válida
-- (su código de asesor no corresponde a ninguna persona de nivel 5).

-- Convierte un texto 'AAAA-MM-DD' en fecha. Devuelve NULL si no es una fecha real
-- (como '0000-00-00') o si el año es absurdo (errores de digitación del origen).
CREATE TEMP FUNCTION fecha_valida(texto STRING) AS (
  IF(
    SAFE_CAST(texto AS DATE) BETWEEN DATE '1900-01-01' AND DATE '2100-12-31',
    SAFE_CAST(texto AS DATE),
    NULL
  )
);

CREATE OR REPLACE TABLE bq_validation.dim_vendedor AS
WITH coordinadora AS (
  SELECT ccodpersona AS id_coordinadora
  FROM bq_staging.persona
  WHERE cnivpersona = '5'
)
SELECT
  p.ccodpersona AS id_vendedor,
  p.cnompersona AS nombre_vendedor,
  p.csexpersona AS sexo,
  fecha_valida(p.dnacpersona) AS fecha_nacimiento,
  NULLIF(TRIM(p.ccodubigeo), '') AS id_ubigeo,
  p.nmovil AS celular,
  IF(p.cnivpersona = '2', NULLIF(p.ccodrelacion, 0), NULL) AS id_lider,
  c.id_coordinadora,
  fecha_valida(p.dfecpersona) AS fecha_ingreso,
  IF(p.cnivpersona = '3', 'Líder', 'Asesora') AS tipo_vendedor
FROM bq_staging.persona AS p
LEFT JOIN coordinadora AS c
  ON c.id_coordinadora = p.ccodasesor
WHERE p.cnivpersona IN ('2', '3');
