"""Dagster definitions for the ArcPy park-access pipeline.

This module is the single entry point loaded by ``dagster-webserver`` and
``dagster-daemon`` (configured via ``dagster_home/workspace.yaml``). It wires
the reusable functions in :mod:`arcpy_orchestration.park_access` into Dagster
ops, assembles them into a job, and attaches a daily schedule.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from dagster import (
    Definitions,
    In,
    Out,
    Output,
    ScheduleDefinition,
    job,
    op,
)

# ---------------------------------------------------------------------------
# Bootstrap: ensure arcpy_orchestration is importable when this file is loaded
# directly by Dagster (which sets its own working directory).
# ---------------------------------------------------------------------------
DIR_PRJ = Path(__file__).parent.parent

if importlib.util.find_spec("arcpy_orchestration") is None:
    src_dir = DIR_PRJ / "src"
    if not src_dir.exists():
        raise EnvironmentError("Unable to import arcpy_orchestration.")
    sys.path.insert(0, str(src_dir))

# Importing the package wires all arcpy_orchestration log output into Python's
# standard logging hierarchy. Dagster captures root-logger records during op
# execution automatically, so log messages from arcpy_orchestration modules
# appear in the Dagster UI without any additional configuration.
import arcpy_orchestration  # noqa: F401, E402
from arcpy_orchestration import park_access  # noqa: E402
from arcpy_orchestration.config import config  # noqa: E402

# ---------------------------------------------------------------------------
# Resolve config-driven inputs once at module scope so individual ops stay
# focused on orchestration rather than path/parameter wiring.
# ---------------------------------------------------------------------------
WORKING_WKID: int = config.spatial.working_wkid
WALK_DISTANCE_M: float = config.park_access.walk_distance_m
VALUE_FIELD: str = config.park_access.value_field

PARKS_FC: str = str(DIR_PRJ / config.park_access.parks_fc)
PARCELS_FC: str = str(DIR_PRJ / config.park_access.parcels_fc)
OUTPUT_PARCELS_FC: str = str(DIR_PRJ / config.park_access.output_parcels_fc)
OUTPUT_SUMMARY_PATH: str = str(DIR_PRJ / config.park_access.output_summary_path)

# Intermediate projected outputs live in the interim FGDB.
_INTERIM_GDB: str = str(DIR_PRJ / "data" / "interim" / "interim.gdb")
PARKS_PROJECTED_FC: str = f"{_INTERIM_GDB}/parks_projected"
PARCELS_PROJECTED_FC: str = f"{_INTERIM_GDB}/parcels_projected"


# ---------------------------------------------------------------------------
# Ops — the individual units of work that make up the pipeline.
# ---------------------------------------------------------------------------

@op(out={"parks_fc": Out(str), "parcels_fc": Out(str)})
def project_inputs(context):
    """Project parks and parcels into the working CRS.

    Yields:
        Output[str]: ``parks_fc`` — path to the projected parks feature class.
        Output[str]: ``parcels_fc`` — path to the projected parcels feature class.
    """
    parks = park_access.project_to_working_crs(
        PARKS_FC, PARKS_PROJECTED_FC, WORKING_WKID
    )
    parcels = park_access.project_to_working_crs(
        PARCELS_FC, PARCELS_PROJECTED_FC, WORKING_WKID
    )
    context.log.info(
        "Projected parks to %s and parcels to %s",
        PARKS_PROJECTED_FC,
        PARCELS_PROJECTED_FC,
    )
    yield Output(parks, output_name="parks_fc")
    yield Output(parcels, output_name="parcels_fc")


@op(ins={"parks_fc": In(str), "parcels_fc": In(str)}, out=Out(str))
def find_parcels_near_parks(
    context,
    parks_fc: str,
    parcels_fc: str,
) -> str:
    """Buffer parks and select parcels within walking distance.

    Args:
        parks_fc: Path to the projected parks feature class.
        parcels_fc: Path to the projected parcels feature class.

    Returns:
        str: Path to the output parcels feature class containing only those
            parcels within walking distance of a park.
    """
    result = park_access.parcels_within_walking_distance(
        parks_fc=parks_fc,
        parcels_fc=parcels_fc,
        out_fc=OUTPUT_PARCELS_FC,
        walk_distance_m=WALK_DISTANCE_M,
        working_wkid=WORKING_WKID,
    )
    context.log.info("Wrote selected parcels to %s", result)
    return result


@op(ins={"parcels_fc": In(str)})
def summarize(context, parcels_fc: str):
    """Compute an overall summary of the selected parcels.

    Args:
        parcels_fc: Path to the feature class produced by
            :func:`find_parcels_near_parks`.

    Returns:
        pandas.DataFrame: One-row summary of parcel count and total value.
    """
    result = park_access.summarize_parcels(
        parcels_fc=parcels_fc,
        value_field=VALUE_FIELD,
    )
    context.log.info("Summarised %d parcels", len(result))
    return result


@op
def export(context, summary_df) -> str:
    """Write the parcel summary to an Excel workbook.

    Args:
        summary_df: Summary DataFrame produced by :func:`summarize`.

    Returns:
        str: Path to the written Excel workbook.
    """
    result = park_access.export_summary(summary_df, OUTPUT_SUMMARY_PATH)
    context.log.info("Exported summary to %s", result)
    return result


# ---------------------------------------------------------------------------
# Job — the ordered pipeline assembled from the ops above.
# ---------------------------------------------------------------------------

@job(
    description=(
        "Refresh the list of parcels within walking distance of a public park "
        "and summarize overall parcel count and value."
    )
)
def park_access_job() -> None:
    """Assemble the four ops into an ordered pipeline."""
    parks_fc, parcels_fc = project_inputs()
    parcels = find_parcels_near_parks(parks_fc=parks_fc, parcels_fc=parcels_fc)
    summary = summarize(parcels_fc=parcels)
    export(summary_df=summary)


# ---------------------------------------------------------------------------
# Schedule — defines when the job runs automatically.
# ---------------------------------------------------------------------------

park_access_daily = ScheduleDefinition(
    job=park_access_job,
    cron_schedule="0 0 * * *",  # midnight daily
    name="park_access_daily",
    execution_timezone="America/Los_Angeles",
)


# ---------------------------------------------------------------------------
# Definitions — top-level object referenced by workspace.yaml.
# ---------------------------------------------------------------------------

defs = Definitions(
    jobs=[park_access_job],
    schedules=[park_access_daily],
)
