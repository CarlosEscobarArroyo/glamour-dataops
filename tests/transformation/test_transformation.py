"""Pruebas de los archivos de src/transformation, sin acceder a BigQuery."""

import csv
from pathlib import Path
import re
import unittest


TRANSFORMACION = Path(__file__).resolve().parents[2] / "src" / "transformation"
COLUMNAS_UBIGEO = ["id_ubigeo", "distrito", "provincia", "departamento", "ubigeo_inei", "observacion"]
OBSERVACIONES = {"", "corregido", "completado a mano", "ambiguo"}


class RefUbigeoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(TRANSFORMACION / "ref_ubigeo.csv", encoding="utf-8", newline="") as archivo:
            lector = csv.DictReader(archivo)
            cls.columnas = lector.fieldnames
            cls.filas = list(lector)

    def test_columns_match_the_schema_loaded_by_the_ci(self):
        self.assertEqual(self.columnas, COLUMNAS_UBIGEO)

    def test_every_row_has_a_unique_code(self):
        codigos = [fila["id_ubigeo"] for fila in self.filas]
        self.assertTrue(all(codigos))
        self.assertEqual(len(codigos), len(set(codigos)))

    def test_inei_code_is_empty_or_six_digits(self):
        invalidos = [f["id_ubigeo"] for f in self.filas if not re.fullmatch(r"(\d{6})?", f["ubigeo_inei"])]
        self.assertEqual(invalidos, [])

    def test_a_district_always_has_province_and_department(self):
        incompletos = [
            f["id_ubigeo"] for f in self.filas
            if f["distrito"] and not (f["provincia"] and f["departamento"])
        ]
        self.assertEqual(incompletos, [])

    def test_observation_uses_a_known_value(self):
        self.assertLessEqual({f["observacion"] for f in self.filas}, OBSERVACIONES)

    def test_values_have_no_surrounding_spaces(self):
        con_espacios = [f["id_ubigeo"] for f in self.filas if any(v != v.strip() for v in f.values())]
        self.assertEqual(con_espacios, [])


class SqlTests(unittest.TestCase):
    def test_each_file_builds_the_validation_table_named_after_it(self):
        archivos = sorted(a for a in TRANSFORMACION.glob("*.sql") if not a.name.startswith("fn_"))
        self.assertTrue(archivos)
        for archivo in archivos:
            with self.subTest(archivo=archivo.name):
                sql = archivo.read_text(encoding="utf-8")
                tablas = re.findall(r"CREATE OR REPLACE TABLE (\S+) AS", sql)
                self.assertEqual(tablas, [f"bq_validation.{archivo.stem}"])
                # Una función temporal choca si dos procedimientos corren en el mismo script.
                self.assertNotIn("TEMP FUNCTION", sql)

    def test_each_function_file_defines_the_function_named_after_it(self):
        for archivo in sorted(TRANSFORMACION.glob("fn_*.sql")):
            with self.subTest(archivo=archivo.name):
                funciones = re.findall(r"CREATE OR REPLACE FUNCTION ([\w.]+)\(", archivo.read_text(encoding="utf-8"))
                self.assertEqual(funciones, [f"bq_validation.{archivo.stem.removeprefix('fn_')}"])


if __name__ == "__main__":
    unittest.main()
