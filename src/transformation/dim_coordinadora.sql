-- Coordinadoras: las personas de nivel 5.

CREATE OR REPLACE TABLE bq_validation.dim_coordinadora AS
SELECT
  ccodpersona AS id_coordinadora,
  cnompersona AS nombre_coordinadora,
  cestpersona AS estado,
  bq_validation.fecha_valida(dnacpersona) AS fecha_nacimiento
FROM bq_staging.persona
WHERE cnivpersona = '5';
