"""Ejecuta la compuerta de calidad y publica Data Docs en Cloud Storage."""

import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from suites import TABLE_CONTRACTS, build_expectations


IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class Config:
    project: str
    dataset: str
    data_docs_bucket: str
    run_id: str


def log_event(event: str, **fields) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def load_config(environ=None) -> Config:
    environ = os.environ if environ is None else environ
    required = ("GCP_PROJECT", "BQ_DATASET", "DATA_DOCS_BUCKET")
    missing = [name for name in required if not environ.get(name, "").strip()]
    if missing:
        raise ValueError("Faltan variables de entorno: " + ", ".join(missing))

    project = environ["GCP_PROJECT"].strip()
    dataset = environ["BQ_DATASET"].strip()
    bucket = environ["DATA_DOCS_BUCKET"].strip()
    for name, value in (
        ("GCP_PROJECT", project),
        ("BQ_DATASET", dataset),
        ("DATA_DOCS_BUCKET", bucket),
    ):
        if not IDENTIFIER.fullmatch(value):
            raise ValueError(f"{name} contiene caracteres no permitidos")

    run_id = environ.get("RUN_ID", "").strip()
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("manual-%Y%m%dT%H%M%SZ")
    if not IDENTIFIER.fullmatch(run_id):
        raise ValueError("RUN_ID contiene caracteres no permitidos")
    return Config(project, dataset, bucket, run_id)


def result_succeeded(result) -> bool:
    success = getattr(result, "success", None)
    if success is None and isinstance(result, dict):
        success = result.get("success")
    return bool(success)


def upload_data_docs(local_site: Path, config: Config, storage_client=None) -> int:
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=config.project)
    client = storage_client
    bucket = client.bucket(config.data_docs_bucket)
    files = [path for path in local_site.rglob("*") if path.is_file()]
    for path in files:
        relative = path.relative_to(local_site).as_posix()
        for prefix in (f"runs/{config.run_id}", "latest"):
            blob = bucket.blob(f"{prefix}/{relative}")
            blob.upload_from_filename(str(path))
    return len(files)


def run_quality(config: Config) -> bool:
    import great_expectations as gx
    import great_expectations.expectations as gxe
    from great_expectations.checkpoint import UpdateDataDocsAction

    workdir = Path(tempfile.mkdtemp(prefix="gx-quality-"))
    try:
        context_root = workdir / "context"
        data_docs_dir = workdir / "data_docs"
        context = gx.get_context(mode="file", project_root_dir=str(context_root))
        context.variables.analytics_enabled = False
        context.variables.save()
        context = gx.get_context(mode="file", project_root_dir=str(context_root))

        site_name = "quality_data_docs"
        context.add_data_docs_site(
            site_name=site_name,
            site_config={
                "class_name": "SiteBuilder",
                "site_index_builder": {"class_name": "DefaultSiteIndexBuilder"},
                "store_backend": {
                    "class_name": "TupleFilesystemStoreBackend",
                    "base_directory": str(data_docs_dir),
                },
            },
        )

        datasource = context.data_sources.add_bigquery(
            name="bigquery_validation",
            connection_string=f"bigquery://{config.project}/{config.dataset}",
        )
        validation_definitions = []
        for table in TABLE_CONTRACTS:
            suite = context.suites.add(gx.ExpectationSuite(name=f"{table}_suite"))
            for expectation in build_expectations(
                gxe, table, config.project, config.dataset
            ):
                suite.add_expectation(expectation)
            asset = datasource.add_table_asset(name=table, table_name=table)
            batch_definition = asset.add_batch_definition_whole_table(
                name=f"{table}_full_table"
            )
            validation_definitions.append(
                context.validation_definitions.add(
                    gx.ValidationDefinition(
                        name=f"{table}_validation",
                        data=batch_definition,
                        suite=suite,
                    )
                )
            )

        checkpoint = context.checkpoints.add(
            gx.Checkpoint(
                name="quality_checkpoint",
                validation_definitions=validation_definitions,
                actions=[
                    UpdateDataDocsAction(
                        name="update_quality_data_docs", site_names=[site_name]
                    )
                ],
                result_format={
                    "result_format": "SUMMARY",
                    "partial_unexpected_count": 0,
                    "return_unexpected_index_query": False,
                    "include_unexpected_rows": False,
                    "exclude_unexpected_values": True,
                },
            )
        )
        result = checkpoint.run()
        uploaded = upload_data_docs(data_docs_dir, config)
        success = result_succeeded(result)
        log_event(
            "quality_finished",
            success=success,
            run_id=config.run_id,
            tables=list(TABLE_CONTRACTS),
            data_docs_files=uploaded,
            data_docs_prefix=f"gs://{config.data_docs_bucket}/runs/{config.run_id}/",
        )
        return success
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    try:
        config = load_config()
        log_event(
            "quality_started",
            run_id=config.run_id,
            project=config.project,
            dataset=config.dataset,
            tables=list(TABLE_CONTRACTS),
        )
        return 0 if run_quality(config) else 1
    except Exception as error:
        log_event("quality_error", error_type=type(error).__name__, message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
