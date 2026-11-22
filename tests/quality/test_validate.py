import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "src" / "quality"
sys.path.insert(0, str(QUALITY))

import validate


VALID_ENV = {
    "GCP_PROJECT": "glamour-dataops-dev",
    "BQ_DATASET": "bq_validation",
    "DATA_DOCS_BUCKET": "glamour-dataops-dev-cs-data-docs",
    "RUN_ID": "test-run-123",
}


class ConfigTests(unittest.TestCase):
    def test_loads_required_configuration(self):
        config = validate.load_config(VALID_ENV)
        self.assertEqual(config.project, "glamour-dataops-dev")
        self.assertEqual(config.run_id, "test-run-123")

    def test_reports_all_missing_variables(self):
        with self.assertRaisesRegex(
            ValueError, "GCP_PROJECT, BQ_DATASET, DATA_DOCS_BUCKET"
        ):
            validate.load_config({})

    def test_rejects_unsafe_identifiers(self):
        with self.assertRaisesRegex(ValueError, "BQ_DATASET"):
            validate.load_config({**VALID_ENV, "BQ_DATASET": "bad.dataset"})

    def test_manual_run_id_is_generated(self):
        config = validate.load_config({k: v for k, v in VALID_ENV.items() if k != "RUN_ID"})
        self.assertRegex(config.run_id, r"^manual-\d{8}T\d{6}Z$")


def expectation_result(success, severity="critical", description="regla", raised=False):
    return SimpleNamespace(
        success=success,
        expectation_config=SimpleNamespace(
            severity=severity, description=description, type="expect_x"
        ),
        exception_info={"raised_exception": raised},
    )


def checkpoint_result(*tables):
    return SimpleNamespace(
        run_results={
            name: SimpleNamespace(asset_name=name, suite_name=f"{name}_suite", results=items)
            for name, items in tables
        }
    )


class EvaluateTests(unittest.TestCase):
    def test_passes_when_every_expectation_passes(self):
        success, tables = validate.evaluate(
            checkpoint_result(("dim_x", [expectation_result(True)]))
        )
        self.assertTrue(success)
        self.assertEqual(tables[0]["critical_failures"], [])

    def test_a_failed_warning_does_not_block(self):
        success, tables = validate.evaluate(
            checkpoint_result(
                ("dim_x", [expectation_result(False, "warning", "aviso"), expectation_result(True)])
            )
        )
        self.assertTrue(success)
        self.assertEqual(tables[0]["warnings"], ["aviso"])

    def test_a_failed_critical_blocks(self):
        success, tables = validate.evaluate(
            checkpoint_result(
                ("dim_x", [expectation_result(True)]),
                ("fact_y", [expectation_result(False, "critical", "clave única")]),
            )
        )
        self.assertFalse(success)
        self.assertEqual(tables[1], {"table": "fact_y", "critical_failures": ["clave única"], "warnings": []})

    def test_a_warning_that_could_not_run_blocks(self):
        success, _ = validate.evaluate(
            checkpoint_result(("dim_x", [expectation_result(False, "warning", raised=True)]))
        )
        self.assertFalse(success)

    def test_nothing_validated_is_not_a_success(self):
        self.assertFalse(validate.evaluate(checkpoint_result())[0])

    def test_reads_a_real_great_expectations_result(self):
        """El checkpoint de GX falla con solo advertencias; evaluate lo aprueba."""
        import great_expectations as gx
        import great_expectations.expectations as gxe

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "datos.db"
            with closing(sqlite3.connect(database)) as conexion:
                conexion.execute("CREATE TABLE dim_x (id INTEGER)")
                conexion.execute("INSERT INTO dim_x VALUES (1), (1)")
                conexion.commit()
            context = gx.get_context(mode="ephemeral")
            asset = context.data_sources.add_sqlite(
                name="local", connection_string=f"sqlite:///{database}"
            ).add_table_asset(name="dim_x", table_name="dim_x")
            suite = context.suites.add(gx.ExpectationSuite(name="dim_x_suite"))
            suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="id"))
            suite.add_expectation(
                gxe.ExpectColumnValuesToBeUnique(column="id", severity="warning")
            )
            definition = context.validation_definitions.add(
                gx.ValidationDefinition(
                    name="dim_x_validation",
                    data=asset.add_batch_definition_whole_table(name="todo"),
                    suite=suite,
                )
            )
            result = context.checkpoints.add(
                gx.Checkpoint(name="prueba", validation_definitions=[definition])
            ).run()

        self.assertFalse(result.success)
        success, tables = validate.evaluate(result)
        self.assertTrue(success)
        self.assertEqual(tables[0]["table"], "dim_x")
        self.assertEqual(tables[0]["warnings"], ["expect_column_values_to_be_unique"])


class ResultTests(unittest.TestCase):
    def test_main_returns_zero_when_quality_passes(self):
        with (
            patch.dict(os.environ, VALID_ENV, clear=True),
            patch.object(validate, "run_quality", return_value=True),
            patch.object(validate, "log_event"),
        ):
            self.assertEqual(validate.main(), 0)

    def test_main_returns_one_when_quality_is_rejected(self):
        with (
            patch.dict(os.environ, VALID_ENV, clear=True),
            patch.object(validate, "run_quality", return_value=False),
            patch.object(validate, "log_event"),
        ):
            self.assertEqual(validate.main(), 1)

    def test_main_returns_one_on_technical_error(self):
        with (
            patch.dict(os.environ, VALID_ENV, clear=True),
            patch.object(validate, "run_quality", side_effect=RuntimeError("boom")),
            patch.object(validate, "log_event") as log,
        ):
            self.assertEqual(validate.main(), 1)
            log.assert_any_call(
                "quality_error", "ERROR", error_type="RuntimeError", message="boom"
            )


class LogSeverityTests(unittest.TestCase):
    def test_each_line_carries_severity_for_cloud_logging(self):
        with patch("builtins.print") as printed:
            validate.log_event("quality_finished", "ERROR", success=False)
        line = json.loads(printed.call_args.args[0])
        self.assertEqual(line, {"severity": "ERROR", "event": "quality_finished", "success": False})

    def test_default_severity_is_info(self):
        with patch("builtins.print") as printed:
            validate.log_event("quality_started", run_id="r")
        self.assertEqual(json.loads(printed.call_args.args[0])["severity"], "INFO")

    def test_severity_reflects_the_worst_failure(self):
        self.assertEqual(validate._severity(1, 3), "ERROR")
        self.assertEqual(validate._severity(0, 2), "WARNING")
        self.assertEqual(validate._severity(0, 0), "INFO")


BASE = "https://storage.cloud.google.com/bucket/latest"


class AbsoluteLinksTests(unittest.TestCase):
    def test_index_links_point_inside_the_prefix(self):
        html = (
            '<a href="expectations/dim_x_suite.html">s</a>'
            '<link href="./static/images/favicon.ico">'
            "{'_table_row_link_path': 'validations/dim_x_suite/__none__/"
            "20261122T174352.582536Z/bigquery_validation-dim_x.html'}"
        )
        result = validate.absolute_links(html, "index.html", BASE)
        self.assertIn(f'href="{BASE}/expectations/dim_x_suite.html"', result)
        self.assertIn(f'href="{BASE}/static/images/favicon.ico"', result)
        self.assertIn(
            f"'{BASE}/validations/dim_x_suite/__none__/"
            "20261122T174352.582536Z/bigquery_validation-dim_x.html'",
            result,
        )

    def test_parent_links_resolve_from_the_page_folder(self):
        page = "validations/s/__none__/20261122T174352.582536Z/x.html"
        result = validate.absolute_links('<a href="../../../../index.html">', page, BASE)
        self.assertEqual(result, f'<a href="{BASE}/index.html">')

    def test_external_and_anchor_links_are_untouched(self):
        html = (
            '<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>'
            '<a href="#section-1">a</a><a href="mailto:x@y.z">m</a>'
        )
        self.assertEqual(validate.absolute_links(html, "index.html", BASE), html)


class DataDocsUploadTests(unittest.TestCase):
    def test_uploads_each_file_to_run_and_latest(self):
        client = MagicMock()
        bucket = client.bucket.return_value
        old_page = MagicMock()
        client.list_blobs.return_value = [old_page]
        blobs = {}

        def blob(name):
            blobs[name] = MagicMock()
            return blobs[name]

        bucket.blob.side_effect = blob
        config = validate.Config(
            "glamour-dataops-dev",
            "bq_validation",
            "glamour-dataops-dev-cs-data-docs",
            "test-run-123",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text('<a href="static/site.css">', encoding="utf-8")
            (root / "static").mkdir()
            (root / "static" / "site.css").write_text("css", encoding="utf-8")
            uploaded = validate.upload_data_docs(root, config, client)

        self.assertEqual(uploaded, 2)
        self.assertEqual(
            set(blobs),
            {
                "runs/test-run-123/index.html",
                "runs/test-run-123/static/site.css",
                "latest/index.html",
                "latest/static/site.css",
            },
        )
        # latest/ se vacía antes de subir la nueva ejecución.
        client.list_blobs.assert_called_once_with(
            "glamour-dataops-dev-cs-data-docs", prefix="latest/"
        )
        old_page.delete.assert_called_once()
        # Las páginas se suben con enlaces completos a su propia carpeta.
        blobs["latest/index.html"].upload_from_string.assert_called_once_with(
            '<a href="https://storage.cloud.google.com/'
            'glamour-dataops-dev-cs-data-docs/latest/static/site.css">',
            content_type="text/html; charset=utf-8",
        )
        run_html = blobs["runs/test-run-123/index.html"].upload_from_string.call_args.args[0]
        self.assertIn("/runs/test-run-123/static/site.css", run_html)
        blobs["latest/static/site.css"].upload_from_filename.assert_called_once()


if __name__ == "__main__":
    unittest.main()
