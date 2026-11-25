-- Ubicaciones: distrito, provincia y departamento de cada código de ubigeo que usa
-- el sistema de Glamour. Sale de ref_ubigeo, una tabla de referencia que se carga
-- desde src/transformation/ref_ubigeo.csv (el origen no trae la provincia).
-- ubigeo_inei es el código oficial del distrito, cuando se conoce.
CREATE OR REPLACE TABLE bq_validation.dim_ubicacion AS
SELECT
  id_ubigeo,
  distrito,
  provincia,
  departamento,
  ubigeo_inei
FROM bq_staging.ref_ubigeo;
