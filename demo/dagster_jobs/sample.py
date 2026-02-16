import random
import time

from dagster import (
    AssetMaterialization,
    MetadataValue,
    OpExecutionContext,
    job,
    op,
    Definitions,
    Config,
)


# ---------------------------------------------------------------------------
# 1. A simple ETL pipeline
# ---------------------------------------------------------------------------


@op
def extract(context: OpExecutionContext):
    """Simulate extracting data from an external source."""
    rows = [{"id": i, "value": random.randint(1, 100)} for i in range(1, 11)]
    context.log.info(f"Extracted {len(rows)} rows")
    return rows


@op
def transform(context: OpExecutionContext, raw_data: list):
    """Apply a simple transformation: double every value."""
    transformed = [{**row, "value": row["value"] * 2} for row in raw_data]
    context.log.info(f"Transformed {len(transformed)} rows")
    return transformed


@op
def load(context: OpExecutionContext, data: list):
    """Simulate loading data into a target system."""
    time.sleep(1)
    context.log.info(f"Loaded {len(data)} rows into target")
    context.log_event(
        AssetMaterialization(
            asset_key="etl_output",
            metadata={
                "row_count": MetadataValue.int(len(data)),
            },
        )
    )


@job
def etl_pipeline():
    """A three-step Extract-Transform-Load pipeline."""
    load(transform(extract()))


# ---------------------------------------------------------------------------
# 2. A report-generation job with config
# ---------------------------------------------------------------------------


class ReportConfig(Config):
    report_name: str = "daily_summary"
    num_sections: int = 3


@op
def generate_report(context: OpExecutionContext, config: ReportConfig):
    """Generate a report with a configurable number of sections."""
    sections = [f"Section {i + 1}" for i in range(config.num_sections)]
    context.log.info(
        f"Generated report '{config.report_name}' with {len(sections)} sections"
    )
    return {"name": config.report_name, "sections": sections}


@op
def publish_report(context: OpExecutionContext, report: dict):
    """Publish the generated report."""
    time.sleep(0.5)
    context.log.info(f"Published report: {report['name']}")
    context.log_event(
        AssetMaterialization(
            asset_key=f"report_{report['name']}",
            metadata={
                "report_name": MetadataValue.text(report["name"]),
                "section_count": MetadataValue.int(len(report["sections"])),
            },
        )
    )


@job
def generate_report_job():
    """Generate and publish a report (supports run config)."""
    publish_report(generate_report())


# ---------------------------------------------------------------------------
# 3. A long-running job (useful for testing cancel)
# ---------------------------------------------------------------------------


@op
def long_running_step(context: OpExecutionContext):
    """Simulate a long-running computation (handy to test cancel)."""
    for i in range(1, 31):
        time.sleep(1)
        context.log.info(f"Progress: {i}/30")


@job
def slow_job():
    """A deliberately slow job — useful for testing cancellation."""
    long_running_step()


# ---------------------------------------------------------------------------
# Definitions (Dagster entry point)
# ---------------------------------------------------------------------------

defs = Definitions(
    jobs=[etl_pipeline, generate_report_job, slow_job],
)
