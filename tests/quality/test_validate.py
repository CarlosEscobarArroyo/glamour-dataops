import os
import sys
import tempfile
import unittest
from pathlib import Path
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


class ResultTests(unittest.TestCase):
    def test_result_status_accepts_objects_and_dictionaries(self):
        success = MagicMock(success=True)
        failure = MagicMock(success=False)
        self.assertTrue(validate.result_succeeded(success))
        self.assertFalse(validate.result_succeeded(failure))
        self.assertTrue(validate.result_succeeded({"success": True}))
        self.assertFalse(validate.result_succeeded({"success": False}))

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
                "quality_error", error_type="RuntimeError", message="boom"
            )


class DataDocsUploadTests(unittest.TestCase):
    def test_uploads_each_file_to_run_and_latest(self):
        client = MagicMock()
        bucket = client.bucket.return_value
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
            (root / "index.html").write_text("index", encoding="utf-8")
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
        for stored_blob in blobs.values():
            stored_blob.upload_from_filename.assert_called_once()


if __name__ == "__main__":
    unittest.main()
