"""Prefect flow definition for flood-zone parcel impact reporting.

This module orchestrates a workflow that:

1. Ensures local raw datasets exist (parcels + FEMA flood zones)
2. Projects both datasets into a shared projected CRS
3. Selects parcels affected by flood zones via spatial intersection
4. Produces a two-sheet Excel report:
   - summary by flood-zone type with affected parcel count and potential dollars
   - detailed records for all affected parcel rows
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from prefect import flow, task

DIR_PRJ = Path(__file__).parent.parent

if importlib.util.find_spec("arcpy_orchestration") is None:
    src_dir = DIR_PRJ / "src"
    if not src_dir.exists():
        raise EnvironmentError("Unable to import arcpy_orchestration.")
    sys.path.insert(0, str(src_dir))

from arcpy_orchestration import flood_zone_summary  # noqa: E402
from arcpy_orchestration.config import config  # noqa: E402
from arcpy_orchestration.orchestration import (  # noqa: E402
    build_prefect_environment,
    export_prefect_environment,
    render_effective_runtime_settings,
    resolve_prefect_runtime_config,
)

WORKING_WKID: int = config.spatial.working_wkid
VALUE_FIELD: str = config.flood_zone_summary.value_field
FLOOD_ZONE_FIELD: str = config.flood_zone_summary.flood_zone_field

FLOOD_ZONES_FC: str = str(DIR_PRJ / config.flood_zone_summary.flood_zones_fc)
PARCELS_FC: str = str(DIR_PRJ / config.flood_zone_summary.parcels_fc)
OUTPUT_AFFECTED_PARCELS_FC: str = str(DIR_PRJ / config.flood_zone_summary.output_parcels_fc)
OUTPUT_SUMMARY_PATH: str = str(DIR_PRJ / config.flood_zone_summary.output_summary_path)

_INTERIM_GDB: str = str(DIR_PRJ / "data" / "interim" / "interim.gdb")
FLOOD_ZONES_PROJECTED_FC: str = f"{_INTERIM_GDB}/flood_zones_projected"
PARCELS_PROJECTED_FC: str = f"{_INTERIM_GDB}/parcels_projected"

FLOW_CONCURRENCY_LIMIT = 1
FLOW_COLLISION_STRATEGY = "ENQUEUE"


def _extract_fgdb_path(dataset_path: Path) -> Path | None:
    """Return the first ``*.gdb`` segment from a dataset path, if present."""
    parts = list(dataset_path.parts)
    for idx, part in enumerate(parts):
        if part.lower().endswith(".gdb"):
            return Path(*parts[: idx + 1])
    return None


RAW_GDB_PATH: Path | None = _extract_fgdb_path(Path(FLOOD_ZONES_FC))


@task
def project_inputs_task() -> tuple[str, str]:
    """Project flood zones and parcels into the working CRS."""
    flood_fc = flood_zone_summary.project_to_working_crs(
        FLOOD_ZONES_FC,
        FLOOD_ZONES_PROJECTED_FC,
        WORKING_WKID,
    )
    parcels_fc = flood_zone_summary.project_to_working_crs(
        PARCELS_FC,
        PARCELS_PROJECTED_FC,
        WORKING_WKID,
    )
    return flood_fc, parcels_fc


@task
def affected_parcels_task(flood_projected: str, parcels_projected: str) -> tuple[str, str]:
    """Generate the affected parcels feature class and resolve zone field."""
    return flood_zone_summary.parcels_affected_by_flood_zones(
        parcels_fc=parcels_projected,
        flood_zones_fc=flood_projected,
        out_fc=OUTPUT_AFFECTED_PARCELS_FC,
        working_wkid=WORKING_WKID,
        flood_zone_field=FLOOD_ZONE_FIELD,
    )


@task
def summarize_flood_impacts_task(affected_parcels_fc: str, resolved_zone_field: str):
    """Build summary and detail DataFrames for the report."""
    return flood_zone_summary.summarize_flood_impacts(
        affected_parcels_fc=affected_parcels_fc,
        flood_zone_field=resolved_zone_field,
        value_field=VALUE_FIELD,
    )


@task
def export_flood_report_task(summary_df, affected_parcels_df) -> str:
    """Write two-sheet Excel report and return output path."""
    return flood_zone_summary.export_flood_impact_report(
        summary_df=summary_df,
        affected_parcels_df=affected_parcels_df,
        out_path=OUTPUT_SUMMARY_PATH,
    )


@flow(name="flood-zone-impact-flow", persist_result=True, log_prints=True)
def flood_zone_impact_flow() -> str:
    """Run the full flood-zone impact workflow."""
    if RAW_GDB_PATH is None:
        raise ValueError(
            "Configured flood_zones_fc path does not include a .gdb segment; "
            "cannot resolve raw geodatabase path."
        )

    flood_zone_summary.prepare_data_directories(project_dir=DIR_PRJ)
    flood_zone_summary.download_raw_data_if_missing(raw_gdb=RAW_GDB_PATH)

    flood_projected, parcels_projected = project_inputs_task()
    affected_parcels_fc, resolved_zone_field = affected_parcels_task(
        flood_projected,
        parcels_projected,
    )
    summary_df, affected_parcels_df = summarize_flood_impacts_task(
        affected_parcels_fc,
        resolved_zone_field,
    )
    return export_flood_report_task(summary_df, affected_parcels_df)


def get_managed_flow_deployment_settings() -> dict[str, object]:
    """Return declarative deployment settings for no-concurrency local execution."""
    return {
        "concurrency_limit": FLOW_CONCURRENCY_LIMIT,
        "collision_strategy": FLOW_COLLISION_STRATEGY,
    }


def serve_flood_zone_impact_flow() -> None:
    """Resolve runtime config and serve flow for worker execution."""
    runtime_config = resolve_prefect_runtime_config()
    export_prefect_environment(build_prefect_environment(runtime_config), overwrite=True)

    print(render_effective_runtime_settings(runtime_config))

    deployment_kwargs = get_managed_flow_deployment_settings()
    try:
        flood_zone_impact_flow.serve(name="flood-zone-impact", **deployment_kwargs)
    except TypeError:
        try:
            flood_zone_impact_flow.serve(
                name="flood-zone-impact",
                concurrency_limit=FLOW_CONCURRENCY_LIMIT,
            )
        except TypeError:
            flood_zone_impact_flow.serve(name="flood-zone-impact")


def run_flood_zone_impact_flow_once() -> str:
    """Execute the flow once in-process (ephemeral Prefect API mode)."""
    runtime_config = resolve_prefect_runtime_config()
    export_prefect_environment(build_prefect_environment(runtime_config), overwrite=True)

    os.environ.pop("PREFECT_API_URL", None)
    os.environ["PREFECT_SERVER_ALLOW_EPHEMERAL_MODE"] = "true"

    print(render_effective_runtime_settings(runtime_config))
    print("Running flood-zone impact flow once in ephemeral (serverless) mode...")

    return flood_zone_impact_flow()


def main(argv: list[str] | None = None) -> None:
    """Dispatch between ``serve`` and ``run`` modes."""
    args = sys.argv[1:] if argv is None else argv
    command = args[0].lower() if args else "serve"

    if command == "run":
        run_flood_zone_impact_flow_once()
    elif command == "serve":
        serve_flood_zone_impact_flow()
    else:
        raise SystemExit(
            f"Unknown command: {command!r}. Use 'serve' (default) or 'run'."
        )


if __name__ == "__main__":
    main()
