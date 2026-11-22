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

    def test_exactly_the_five_pilot_tables_have_deep_rules(self):
        self.assertEqual(
            suites.PILOT_TABLES,
            {
                "dim_fecha",
                "dim_campana",
                "dim_ubicacion",
                "dim_vendedor",
                "fact_pedidos",
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
