import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "src" / "quality"
sys.path.insert(0, str(QUALITY))

import suites


EXPECTED_TABLES = {
    "dim_fecha",
    "dim_campana",
    "dim_producto",
    "dim_variante",
    "dim_coordinadora",
    "dim_ubicacion",
    "dim_vendedor",
    "fact_pedidos",
    "fact_pedidos_detalle",
    "fact_stock_actual",
    "fact_movimientos_stock",
}


class FakeExpectations:
    def __getattr__(self, name):
        def build(**kwargs):
            return {"type": name, **kwargs}

        return build


class SuiteContractTests(unittest.TestCase):
    def test_all_model_tables_have_a_contract(self):
        self.assertEqual(set(suites.TABLE_CONTRACTS), EXPECTED_TABLES)

    def test_contracts_cover_the_workflow_model_tables(self):
        workflow = (ROOT / "src" / "orchestration" / "workflow_comercial.yaml").read_text(
            encoding="utf-8"
        )
        block = workflow.split("- tablas_modelo:", 1)[1].split("- job:", 1)[0]
        workflow_tables = {
            line.strip().removeprefix("- ")
            for line in block.splitlines()
            if line.strip().startswith("- ")
        }
        self.assertEqual(set(suites.TABLE_CONTRACTS), workflow_tables)

    def test_pilot_and_its_extension_have_deep_rules(self):
        self.assertEqual(
            suites.PILOT_TABLES,
            {
                "dim_fecha",
                "dim_campana",
                "dim_ubicacion",
                "dim_vendedor",
                "fact_pedidos",
                "dim_producto",
                "fact_pedidos_detalle",
            },
        )
        self.assertEqual(set(suites.PILOT_BUILDERS), set(suites.PILOT_TABLES))

    def test_every_table_has_non_empty_schema_and_key(self):
        for table, contract in suites.TABLE_CONTRACTS.items():
            with self.subTest(table=table):
                self.assertTrue(contract.columns)
                self.assertTrue(contract.key)
                self.assertTrue(set(contract.key).issubset(contract.columns))
                self.assertEqual(len(contract.columns), len(set(contract.columns)))

    def test_every_table_builds_structural_expectations(self):
        gx = FakeExpectations()
        for table in EXPECTED_TABLES:
            with self.subTest(table=table):
                expectations = suites.build_expectations(
                    gx, table, "glamour-dataops-dev", "bq_validation"
                )
                types = {item["type"] for item in expectations}
                self.assertIn("ExpectTableRowCountToBeBetween", types)
                self.assertIn("ExpectTableColumnsToMatchSet", types)
                self.assertIn("ExpectColumnValuesToNotBeNull", types)

    def test_foreign_key_queries_use_qualified_tables(self):
        expectations = suites.build_expectations(
            FakeExpectations(),
            "fact_pedidos",
            "glamour-dataops-dev",
            "bq_validation",
        )
        queries = [
            item["unexpected_rows_query"]
            for item in expectations
            if item["type"] == "UnexpectedRowsExpectation"
        ]
        self.assertTrue(queries)
        self.assertTrue(
            any(
                "`glamour-dataops-dev.bq_validation.dim_campana`" in query
                for query in queries
            )
        )

    def test_only_known_source_defects_are_warnings(self):
        warnings = {}
        for table in EXPECTED_TABLES:
            for item in suites.build_expectations(
                FakeExpectations(), table, "glamour-dataops-dev", "bq_validation"
            ):
                if item.get("severity") == suites.WARNING:
                    self.assertTrue(item["description"].startswith(suites.WARNING_PREFIX))
                    warnings.setdefault(table, []).append(item["type"])
        self.assertEqual(
            warnings,
            {
                "dim_campana": ["UnexpectedRowsExpectation"],
                "dim_ubicacion": ["UnexpectedRowsExpectation"],
                "fact_pedidos": ["ExpectColumnValuesToBeInSet", "UnexpectedRowsExpectation"],
                "fact_pedidos_detalle": ["UnexpectedRowsExpectation"],
            },
        )

    def test_orders_cover_referential_integrity_and_ranges(self):
        queries = [
            item["unexpected_rows_query"]
            for item in suites.build_expectations(
                FakeExpectations(), "fact_pedidos", "glamour-dataops-dev", "bq_validation"
            )
            if item["type"] == "UnexpectedRowsExpectation" and "severity" not in item
        ]
        text = "\n".join(queries)
        for dimension in ("dim_campana", "dim_fecha", "dim_ubicacion", "dim_coordinadora"):
            with self.subTest(dimension=dimension):
                self.assertIn(f"`glamour-dataops-dev.bq_validation.{dimension}`", text)
        self.assertIn("monto_total_pedido < 0", text)
        self.assertIn("monto_total_pedido - monto_comision + monto_envio", text)
        self.assertIn("CURRENT_DATE('America/Lima')", text)

    def test_detail_lines_must_belong_to_an_order(self):
        critical = [
            item["unexpected_rows_query"]
            for item in suites.build_expectations(
                FakeExpectations(), "fact_pedidos_detalle", "glamour-dataops-dev", "bq_validation"
            )
            if item["type"] == "UnexpectedRowsExpectation" and "severity" not in item
        ]
        self.assertEqual(len(critical), 1)
        self.assertIn("`glamour-dataops-dev.bq_validation.fact_pedidos`", critical[0])

    def test_location_only_requires_names_for_district_codes(self):
        expectations = suites.build_expectations(
            FakeExpectations(), "dim_ubicacion", "glamour-dataops-dev", "bq_validation"
        )
        not_null = {
            item["column"] for item in expectations if item["type"] == "ExpectColumnValuesToNotBeNull"
        }
        self.assertEqual(not_null, {"id_ubigeo"})
        critical = [
            item["unexpected_rows_query"]
            for item in expectations
            if item["type"] == "UnexpectedRowsExpectation" and "severity" not in item
        ]
        self.assertEqual(len(critical), 1)
        self.assertIn("NOT ENDS_WITH(id_ubigeo, '0000')", critical[0])

    def test_pinned_gx_version_accepts_every_expectation(self):
        import great_expectations.expectations as gxe

        for table in EXPECTED_TABLES:
            with self.subTest(table=table):
                self.assertTrue(
                    suites.build_expectations(
                        gxe, table, "glamour-dataops-dev", "bq_validation"
                    )
                )


if __name__ == "__main__":
    unittest.main()
