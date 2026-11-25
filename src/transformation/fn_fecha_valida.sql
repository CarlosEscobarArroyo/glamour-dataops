-- Convierte un texto 'AAAA-MM-DD' en fecha. Devuelve NULL si no es una fecha real
-- (como '0000-00-00') o si el año es absurdo (errores de digitación del origen).
-- La usan las dimensiones y los hechos para todas las fechas que vienen del origen.
CREATE OR REPLACE FUNCTION bq_validation.fecha_valida(texto STRING) AS (
  IF(
    SAFE_CAST(texto AS DATE) BETWEEN DATE '1900-01-01' AND DATE '2100-12-31',
    SAFE_CAST(texto AS DATE),
    NULL
  )
);
