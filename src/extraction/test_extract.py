from contextlib import redirect_stdout
from decimal import Decimal
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

import extract as extraction


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="glamour-config-test-")
        self.addCleanup(directory.cleanup)
        self.config_path = Path(directory.name) / "config_dev.json"
        config_patch = patch.object(extraction, "CONFIG_PATH", self.config_path)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        self.log_patch = patch.object(extraction, "log_event")
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)

    def connection(self, columns, batches):
        connection = MagicMock()
        metadata = MagicMock()
        metadata.__enter__.return_value = metadata
        metadata.fetchall.return_value = columns
        stream = MagicMock()
        stream.__enter__.return_value = stream
        stream.fetchmany.side_effect = batches
        connection.cursor.side_effect = lambda *args: stream if args else metadata
        return connection, stream

    def capturing_bucket(self):
        bucket = MagicMock()
        uploaded = {}

        def blob(name):
            result = MagicMock()

            def upload(filename, **kwargs):
                self.assertEqual(kwargs["if_generation_match"], 0)
                uploaded[name] = pq.read_table(filename)

            result.upload_from_filename.side_effect = upload
            return result

        bucket.blob.side_effect = blob
        return bucket, uploaded

    def test_parquet_preserves_large_integers_decimals_and_null_first_batch(self):
        columns = [
            ("id", "bigint", "bigint unsigned", 20, 0, "YES"),
            ("importe", "decimal", "decimal(22,4)", 22, 4, "YES"),
            ("nombre", "varchar", "varchar(255)", None, None, "YES"),
        ]
        amount = Decimal("123456789012345678.1234")
        connection, stream = self.connection(
            columns, [[(2**64 - 1, amount, None)], [(None, None, "María")], []]
        )
        bucket, uploaded = self.capturing_bucket()
        result = extraction.extraer_tabla(connection, bucket, "persona", "run", 1)

        self.assertEqual(result["rows"], 2)
        self.assertEqual(len(result["objects"]), 2)
        parts = list(uploaded.values())
        self.assertEqual(parts[0].schema, parts[1].schema)
        self.assertEqual(parts[0]["id"].to_pylist(), [2**64 - 1])
        self.assertEqual(parts[0]["importe"].to_pylist(), [amount])
        self.assertEqual(parts[0]["nombre"].to_pylist(), [None])
        self.assertEqual(parts[1]["nombre"].to_pylist(), ["María"])
        self.assertTrue(all(call.args == (1,) for call in stream.fetchmany.call_args_list))

    def test_empty_table_still_has_a_typed_parquet_file(self):
        connection, _ = self.connection(
            [("id", "int", "int", 10, 0, "NO")], [[]]
        )
        bucket, uploaded = self.capturing_bucket()
        result = extraction.extraer_tabla(connection, bucket, "persona", "run", 10)
        self.assertEqual(result["rows"], 0)
        table = uploaded["run/persona/part-00000.parquet"]
        self.assertEqual(table.num_rows, 0)
        self.assertEqual(table.schema, pa.schema([pa.field("id", pa.int64(), False)]))

    def test_time_uses_text_to_preserve_mariadb_durations(self):
        connection, stream = self.connection(
            [("duracion", "time", "time(6)", None, None, "YES")],
            [[("-838:59:59.123456",)], []],
        )
        bucket, uploaded = self.capturing_bucket()
        extraction.extraer_tabla(connection, bucket, "persona", "run", 10)
        self.assertIn("CAST(`duracion` AS CHAR)", stream.execute.call_args.args[0])
        table = next(iter(uploaded.values()))
        self.assertEqual(table["duracion"].to_pylist(), ["-838:59:59.123456"])

    def test_failure_does_not_publish_a_complete_manifest(self):
        bucket = MagicMock()
        with patch.object(extraction, "extraer_tabla", side_effect=RuntimeError("upload")):
            with self.assertRaises(RuntimeError):
                extraction.extraer_datos_mysql(MagicMock(), bucket, "run", 100)
        bucket.blob.assert_not_called()

    def test_success_manifest_covers_exactly_the_five_legacy_tables(self):
        bucket = MagicMock()
        expected = ["persona", "contenido", "campana", "documento", "documentodetalle"]
        with patch.object(extraction, "extraer_tabla", return_value={"rows": 0, "objects": []}) as extract:
            extraction.extraer_datos_mysql(MagicMock(), bucket, "run", 100)
        self.assertEqual([call.args[2] for call in extract.call_args_list], expected)
        bucket.blob.assert_called_once_with("run/manifest.json")
        upload = bucket.blob.return_value.upload_from_string.call_args
        manifest = json.loads(upload.args[0])
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(list(manifest["tables"]), expected)
        self.assertEqual(upload.kwargs["if_generation_match"], 0)

    def test_upload_failure_stops_before_reading_another_batch(self):
        connection, stream = self.connection(
            [("id", "int", "int", 10, 0, "NO")], [[(1,)], [(2,)]]
        )
        bucket = MagicMock()
        bucket.blob.return_value.upload_from_filename.side_effect = RuntimeError("upload")
        with self.assertRaises(RuntimeError):
            extraction.extraer_tabla(connection, bucket, "persona", "run", 1)
        stream.fetchmany.assert_called_once_with(1)

    def test_job_returns_failure_without_logging_source_values(self):
        self.log_patch.stop()
        output = io.StringIO()
        with patch.object(extraction, "ejecutar_extraccion", side_effect=ValueError("sensitive row value")):
            with redirect_stdout(output):
                code = extraction.main()
        self.assertEqual(code, 1)
        self.assertNotIn("sensitive row value", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["severity"], "ERROR")

    def test_invalid_configuration_fails_before_authenticating(self):
        cases = [
            {"GCS_BUCKET": ""},
            {"GCS_BUCKET": "gs://landing"},
            {"GCS_BUCKET": "landing", "EXTRACTION_BATCH_SIZE": "0"},
            {"GCS_BUCKET": "landing", "EXTRACTION_BATCH_SIZE": "invalid"},
            {"GCS_BUCKET": "landing", "CLOUD_RUN_TASK_COUNT": "2"},
        ]
        for environment in cases:
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    with patch.object(extraction.google.auth, "default") as auth:
                        self.assertEqual(extraction.main(), 1)
                        auth.assert_not_called()

    def test_local_config_preserves_secret_names_and_allows_environment_override(self):
        self.config_path.write_text(json.dumps({
            "GOOGLE_CLOUD_PROJECT": "project-dev",
            "GCS_BUCKET": "landing-dev",
            "EXTRACTION_BATCH_SIZE": 100,
            "secrets": {"MYSQL_PASSWORD": "MYSQL_PASSWORD_DEV"},
        }), encoding="utf-8")
        with patch.dict(os.environ, {"GCS_BUCKET": "landing-override"}, clear=True):
            config = extraction.cargar_config()
        self.assertEqual(config["GOOGLE_CLOUD_PROJECT"], "project-dev")
        self.assertEqual(config["GCS_BUCKET"], "landing-override")
        self.assertEqual(config["EXTRACTION_BATCH_SIZE"], 100)
        self.assertEqual(config["secrets"]["MYSQL_PASSWORD"], "MYSQL_PASSWORD_DEV")
        self.assertEqual(config["secrets"]["MYSQL_HOST"], "MYSQL_HOST")

    def test_custom_names_fetch_secret_values_before_connecting_to_mysql(self):
        names = {key: f"{key}_DEV" for key in extraction.MYSQL_SECRET_KEYS}
        values = [b"db.example.test", b"reader", b"test-password", b"glamour", b"3306"]
        secrets = MagicMock()
        responses = []
        for value in values:
            response = MagicMock()
            response.payload.data = value
            responses.append(response)
        secrets.access_secret_version.side_effect = responses

        with patch.object(extraction.pymysql, "connect") as connect:
            extraction.conectar_mysql(secrets, "project-dev", names)

        resources = [
            call.kwargs["request"]["name"]
            for call in secrets.access_secret_version.call_args_list
        ]
        self.assertEqual(resources, [
            f"projects/project-dev/secrets/{name}/versions/latest"
            for name in names.values()
        ])
        self.assertEqual(connect.call_args.kwargs["host"], "db.example.test")
        self.assertEqual(connect.call_args.kwargs["password"], "test-password")
        self.assertEqual(connect.call_args.kwargs["port"], 3306)

    def test_missing_local_file_uses_cloud_run_environment(self):
        with patch.dict(os.environ, {"GCS_BUCKET": "landing-cloud"}, clear=True):
            config = extraction.cargar_config()
        self.assertEqual(config["GCS_BUCKET"], "landing-cloud")
        self.assertEqual(config["secrets"], {key: key for key in extraction.MYSQL_SECRET_KEYS})

    def test_invalid_local_json_fails_before_authenticating(self):
        for content in ("{invalid-json", "[]", '{"secrets": "invalid"}'):
            with self.subTest(content=content):
                self.config_path.write_text(content, encoding="utf-8")
                with patch.object(extraction.google.auth, "default") as auth:
                    self.assertEqual(extraction.main(), 1)
                    auth.assert_not_called()


if __name__ == "__main__":
    unittest.main()
