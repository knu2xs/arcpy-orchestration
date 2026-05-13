"""Dagster asset definitions for the ArcPy park-access pipeline.

This module is the single entry point loaded by ``dagster-webserver`` and
``dagster-daemon`` (configured via ``dagster_home/workspace.yaml``). It wires
the reusable functions in :mod:`arcpy_orchestration.park_access` into Dagster
assets, assembles them into a job via asset selection, and attaches a daily
schedule.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext

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
# standard logging hierarchy. Dagster captures root-logger records during asset
# execution automatically, so log messages from arcpy_orchestration modules
# appear in the Dagster UI without any additional configuration.
import arcpy_orchestration  # noqa: F401, E402
from arcpy_orchestration import park_access  # noqa: E402
from arcpy_orchestration.config import config  # noqa: E402

# ---------------------------------------------------------------------------
# Resolve config-driven inputs once at module scope so individual assets stay
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
# Assets — each function produces one named, trackable output in the catalog.
# ---------------------------------------------------------------------------

@dg.multi_asset(
    outs={
        "parks_projected": dg.AssetOut(
            dagster_type=str,
            description="Parks feature class projected into the working CRS.",
        ),
        "parcels_projected": dg.AssetOut(
            dagster_type=str,
            description="Parcels feature class projected into the working CRS.",
        ),
    },
    group_name="park_access",
)
def project_inputs(context: AssetExecutionContext) -> tuple[str, str]:
    """Project parks and parcels into the working CRS.

    Returns:
        tuple[str, str]: Paths to the projected parks and parcels feature
            classes, bound to the ``parks_projected`` and
            ``parcels_projected`` asset keys respectively.
    """
    parks = park_access.project_to_working_crs(
        PARKS_FC, PARKS_PROJECTED_FC, WORKING_WKID
    )
    parcels = park_access.project_to_working_crs(
        PARCELS_FC, PARCELS_PROJECTED_FC, WORKING_WKID
    )
    context.log.info(
        "Projected parks → %s and parcels → %s",
        PARKS_PROJECTED_FC,
        PARCELS_PROJECTED_FC,
    )
    return parks, parcels


@dg.asset(
    group_name="park_access",
    description="Parcels that fall within walking distance of a public park.",
)
def parcels_near_parks(
    context: AssetExecutionContext,
    parks_projected: str,
    parcels_projected: str,
) -> str:
    """Buffer parks and select parcels within walking distance.

    Args:
        parks_projected: Path to the projected parks feature class (from
            :func:`project_inputs`).
        parcels_projected: Path to the projected parcels feature class (from
            :func:`project_inputs`).

    Returns:
        str: Path to the output feature class of selected parcels.
    """
    result = park_access.parcels_within_walking_distance(
        parks_fc=parks_projected,
        parcels_fc=parcels_projected,
        out_fc=OUTPUT_PARCELS_FC,
        walk_distance_m=WALK_DISTANCE_M,
        working_wkid=WORKING_WKID,
    )
    context.log.info("Wrote selected parcels to %s", result)
    return result


@dg.asset(
    group_name="park_access",
    description="Summary statistics (count, total value, mean value) for parcels near parks.",
)
def parcel_summary(
    context: AssetExecutionContext,
    parcels_near_parks: str,
):
    """Compute an overall summary of the selected parcels.

    Args:
        parcels_near_parks: Path to the feature class produced by
            :func:`parcels_near_parks`.

    Returns:
        pandas.DataFrame: One-row summary with ``parcel_count``,
            ``total_value``, and ``mean_value`` columns.
    """
    result = park_access.summarize_parcels(
        parcels_fc=parcels_near_parks,
        value_field=VALUE_FIELD,
    )
    context.log.info("Summarised %d parcels", len(result))
    return result


@dg.asset(
    group_name="park_access",
    description="Excel workbook summarising parcels near parks.",
)
def summary_excel(
    context: AssetExecutionContext,
    parcel_summary,
) -> str:
    """Write the parcel summary to an Excel workbook.

    Args:
        parcel_summary: Summary DataFrame produced by :func:`parcel_summary`.

    Returns:
        str: Path to the written Excel workbook.
    """
    result = park_access.export_summary(parcel_summary, OUTPUT_SUMMARY_PATH)
    context.log.info("Exported summary to %s", result)
    return result


# ---------------------------------------------------------------------------
# Job — select all assets in the group and run them as a single job.
# ---------------------------------------------------------------------------

park_access_job = dg.define_asset_job(
    name="park_access_job",
    selection=dg.AssetSelection.groups("park_access"),
    description=(
        "Refresh the list of parcels within walking distance of a public park "
        "and summarize overall parcel count and value."
    ),
)


# ---------------------------------------------------------------------------
# Schedule — defines when the job runs automatically.
# ---------------------------------------------------------------------------

park_access_daily = dg.ScheduleDefinition(
    job=park_access_job,
    cron_schedule="0 0 * * *",  # midnight daily
    name="park_access_daily",
    execution_timezone="America/Los_Angeles",
)


# ---------------------------------------------------------------------------
# Definitions — top-level object referenced by workspace.yaml.
# ---------------------------------------------------------------------------

defs = dg.Definitions(
    assets=[project_inputs, parcels_near_parks, parcel_summary, summary_excel],
    jobs=[park_access_job],
    schedules=[park_access_daily],
)
