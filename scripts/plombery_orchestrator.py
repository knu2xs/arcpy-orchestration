# import core Python libraries
import importlib.util
from pathlib import Path
import sys

# import third-party libraries
from apscheduler.triggers.interval import IntervalTrigger
from plombery import task, Trigger, register_pipeline

# path to the root of the project
DIR_PRJ = Path(__file__).parent.parent

# if the project package is not installed in the environment, add the source directory to the system path
if importlib.util.find_spec('arcpy_orchestration') is None:

    # get the relative path to where the source directory is located
    src_dir = DIR_PRJ / 'src'

    # throw an error if the source directory cannot be located
    if not src_dir.exists():
        raise EnvironmentError('Unable to import arcpy_orchestration.')

    # add the source directory to the paths searched when importing
    sys.path.insert(0, str(src_dir))

# Importing the package wires all arcpy_orchestration log output into the active
# Plombery run logger so messages appear in the Plombery web UI. See
# `docsrc/mkdocs/plombery_logging_integration.md` for details.
import arcpy_orchestration  # noqa: F401, E402
from arcpy_orchestration import park_access  # noqa: E402
from arcpy_orchestration.config import config  # noqa: E402

# ---------------------------------------------------------------------------
# Resolve config-driven inputs once at module scope so individual tasks stay
# focused on orchestration rather than path/parameter wiring.
# ---------------------------------------------------------------------------
WORKING_WKID: int = config.spatial.working_wkid
WALK_DISTANCE_M: float = config.park_access.walk_distance_m
VALUE_FIELD: str = config.park_access.value_field

PARKS_FC = str(DIR_PRJ / config.park_access.parks_fc)
PARCELS_FC = str(DIR_PRJ / config.park_access.parcels_fc)
OUTPUT_PARCELS_FC = str(DIR_PRJ / config.park_access.output_parcels_fc)
OUTPUT_SUMMARY_PATH = str(DIR_PRJ / config.park_access.output_summary_path)

# Intermediate projected outputs live in the interim FGDB.
_INTERIM_GDB = str(DIR_PRJ / "data" / "interim" / "interim.gdb")
PARKS_PROJECTED_FC = f"{_INTERIM_GDB}/parks_projected"
PARCELS_PROJECTED_FC = f"{_INTERIM_GDB}/parcels_projected"


# ---------------------------------------------------------------------------
# Pipeline tasks
# ---------------------------------------------------------------------------
# Each task delegates to a reusable arcpy_orchestration.park_access function.
# The functions emit their own log messages, which propagate to the Plombery
# UI via the package-level PlomberyHandler.
# ---------------------------------------------------------------------------

@task
async def project_inputs() -> dict[str, str]:
    """Project parks and parcels into the working CRS."""
    parks = park_access.project_to_working_crs(
        PARKS_FC, PARKS_PROJECTED_FC, WORKING_WKID
    )
    parcels = park_access.project_to_working_crs(
        PARCELS_FC, PARCELS_PROJECTED_FC, WORKING_WKID
    )
    return {"parks_fc": parks, "parcels_fc": parcels}


@task
async def find_parcels_near_parks(projected: dict[str, str]) -> str:
    """Buffer parks and select parcels within walking distance."""
    return park_access.parcels_within_walking_distance(
        parks_fc=projected["parks_fc"],
        parcels_fc=projected["parcels_fc"],
        out_fc=OUTPUT_PARCELS_FC,
        walk_distance_m=WALK_DISTANCE_M,
        working_wkid=WORKING_WKID,
    )


@task
async def summarize(parcels_fc: str):
    """Compute an overall summary of the selected parcels."""
    return park_access.summarize_parcels(
        parcels_fc=parcels_fc,
        value_field=VALUE_FIELD,
    )


@task
async def export(summary_df) -> str:
    """Write the parcel summary to an Excel workbook."""
    return park_access.export_summary(summary_df, OUTPUT_SUMMARY_PATH)


register_pipeline(
    id="park_access_pipeline",
    description=(
        "Refresh the list of parcels within walking distance of a public park "
        "and summarize overall parcel count and value."
    ),
    tasks=[project_inputs, find_parcels_near_parks, summarize, export],
    triggers=[
        Trigger(
            id="daily",
            name="Daily",
            description="Run the pipeline once per day.",
            schedule=IntervalTrigger(days=1),
        ),
    ],
)


if __name__ == "__main__":
    # Start the Plombery web app (FastAPI under uvicorn). This block is what
    # Servy invokes when running the orchestrator as a Windows service. Reload
    # is intentionally disabled — Uvicorn's reloader spawns subprocesses, which
    # is unstable on Windows inside managed/conda Python environments.
    import uvicorn

    uvicorn.run(
        "plombery:get_app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        factory=True,
    )