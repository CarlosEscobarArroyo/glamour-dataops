from contextlib import redirect_stdout
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pymysql

# tests/ replica la estructura de src/: el código probado vive en src/extraction/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "extraction"))

import extract as extraction  # noqa: E402


ENTORNO = {
    "GCS_BUCKET": "landing",
    "MYSQL_HOST": "db.example.test",
    "MYSQL_USER": "reader",
    "MYSQL_PASSWORD": "test-password",
    "MYSQL_DATABASE": "glamour",
    "MYSQL_PORT": "3306",
}


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.log_patch = patch.object(extraction, "log_event")
        self.log_event = self.log_patch.start()
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
            [("id", "int", "int", 10, 0, "NO")], [[], []]
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

    def test_zero_dates_are_preserved_as_text(self):
        columns = [
            ("dfecha", "date", "date", None, None, "YES"),
            ("dregistro", "datetime", "datetime", None, None, "YES"),
            ("dmodifica", "timestamp", "timestamp", None, None, "NO"),
        ]
        row = ("0000-00-00", "0000-00-00 00:00:00", "2026-10-30 12:00:00")
        connection, stream = self.connection(columns, [[row], []])
        bucket, uploaded = self.capturing_bucket()
        extraction.extraer_tabla(connection, bucket, "campana", "run", 10)
        query = stream.execute.call_args.args[0]
        for name, *_ in columns:
            self.assertIn(f"CAST(`{name}` AS CHAR) AS `{name}`", query)
        table = next(iter(uploaded.values()))
        self.assertEqual(table.to_pylist(), [dict(zip(table.schema.names, row))])
        self.assertTrue(all(field.type == pa.string() for field in table.schema))

    def test_failure_does_not_publish_a_complete_manifest(self):
        bucket = MagicMock()
        with patch.object(extraction, "extraer_tabla", side_effect=[{"rows": 1}, RuntimeError("upload")]):
            with self.assertRaises(RuntimeError):
                extraction.extraer_datos_mysql(MagicMock(), bucket, "run", 100)
        bucket.blob.assert_not_called()

    def test_missing_selected_table_fails_without_publishing_manifest(self):
        connection, _ = self.connection([], [])
        bucket = MagicMock()
        with self.assertRaisesRegex(ValueError, "No se encontró el esquema"):
            extraction.extraer_datos_mysql(connection, bucket, "run", 100)
        bucket.blob.assert_not_called()

    def test_success_manifest_covers_only_the_18_selected_tables(self):
        bucket = MagicMock()
        expected = [
            "persona", "contenido", "campana", "documento", "documentodetalle",
            "stockcontrol", "stockmovi", "stocknotas", "contenidoprenda",
            "campanarangos", "sventas", "personasaldos", "webparametros",
            "webmodulos", "pagepagos", "seccion", "seccioncontenido", "documentofile",
        ]
        with patch.object(extraction, "extraer_tabla", return_value={"rows": 0, "objects": []}) as extract:
            extraction.extraer_datos_mysql(MagicMock(), bucket, "run", 100)
        self.assertEqual([call.args[2] for call in extract.call_args_list], expected)
        bucket.blob.assert_called_once_with("run/manifest.json")
        upload = bucket.blob.return_value.upload_from_string.call_args
        manifest = json.loads(upload.args[0])
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(list(manifest["tables"]), expected)
        self.assertEqual(manifest["selected_tables"], expected)
        self.assertEqual(manifest["scope"], "selected_tables")
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
        with (
            patch.dict(os.environ, ENTORNO, clear=True),
            patch.object(extraction, "ejecutar_extraccion", side_effect=ValueError("sensitive row value")),
            redirect_stdout(output),
        ):
            code = extraction.main()
        self.assertEqual(code, 1)
        self.assertNotIn("sensitive row value", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["severity"], "ERROR")

    def test_missing_variables_are_named_and_stop_before_extracting(self):
        entorno = {k: v for k, v in ENTORNO.items() if k not in ("MYSQL_HOST", "MYSQL_PORT")}
        entorno["GCS_BUCKET"] = ""  # una variable vacía también cuenta como ausente
        with (
            patch.dict(os.environ, entorno, clear=True),
            patch.object(extraction, "ejecutar_extraccion") as run,
        ):
            self.assertEqual(extraction.main(), 1)
        run.assert_not_called()
        self.assertEqual(
            self.log_event.call_args.kwargs["message"],
            "Faltan variables de entorno: GCS_BUCKET, MYSQL_HOST, MYSQL_PORT",
        )

    def test_connection_uses_environment_values(self):
        with (
            patch.dict(os.environ, ENTORNO, clear=True),
            patch.object(extraction.pymysql, "connect") as connect,
        ):
            extraction.conectar_mysql()
        kwargs = connect.call_args.kwargs
        self.assertEqual(kwargs["host"], "db.example.test")
        self.assertEqual(kwargs["user"], "reader")
        self.assertEqual(kwargs["password"], "test-password")
        self.assertEqual(kwargs["database"], "glamour")
        self.assertEqual(kwargs["port"], 3306)

    def test_connection_failure_logs_the_cause_without_the_password(self):
        error = pymysql.err.OperationalError(
            1045, "Access denied for user 'reader'@'10.0.0.1' (using password: YES)"
        )
        with (
            patch.dict(os.environ, ENTORNO, clear=True),
            patch.object(extraction.pymysql, "connect", side_effect=error),
            self.assertRaises(pymysql.MySQLError),
        ):
            extraction.conectar_mysql()
        call = self.log_event.call_args
        self.assertEqual(call.args[0], "mysql_connection_failed")
        self.assertIn("Access denied", call.kwargs["message"])
        self.assertNotIn("test-password", call.kwargs["message"])

    def test_non_numeric_port_is_reported_as_a_connection_failure(self):
        with (
            patch.dict(os.environ, {**ENTORNO, "MYSQL_PORT": "abc"}, clear=True),
            patch.object(extraction.pymysql, "connect") as connect,
            self.assertRaises(ValueError),
        ):
            extraction.conectar_mysql()
        connect.assert_not_called()
        self.assertEqual(self.log_event.call_args.args[0], "mysql_connection_failed")

    def run_prefix_usado(self, entorno):
        with (
            patch.dict(os.environ, entorno, clear=True),
            patch.object(extraction.storage, "Client"),
            patch.object(extraction, "conectar_mysql"),
            patch.object(extraction, "extraer_datos_mysql") as extraer,
        ):
            extraction.ejecutar_extraccion()
        return extraer.call_args.args[2]

    def test_run_prefix_from_the_workflow_is_used_as_is(self):
        prefix = self.run_prefix_usado({**ENTORNO, "RUN_PREFIX": "date=2026-11-21/abc"})
        self.assertEqual(prefix, "date=2026-11-21/abc")

    def test_run_prefix_is_generated_when_the_workflow_does_not_send_one(self):
        prefix = self.run_prefix_usado(ENTORNO)
        self.assertRegex(prefix, r"^date=\d{4}-\d{2}-\d{2}/\d{8}T\d{6}-[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
