"""Prefect flow definition for the park-access data pipeline.

This module wraps the existing ``arcpy_orchestration.park_access`` pipeline in a
Prefect flow so it can be scheduled, monitored, and triggered through the Prefect
UI instead of being run as a one-off script. Each logical step of the pipeline is
exposed as a Prefect ``@task`` and composed together inside a single ``@flow``.

The module can be used two ways:

- **Imported** — other code (for example, the smoke-test script) imports
  ``park_access_flow`` and calls it directly.
- **Executed** — running ``python scripts/make_data_prefect.py`` accepts a
  command:

    - ``serve`` (the default) calls :func:`serve_park_access_flow`, which exports
      the resolved Prefect environment and serves the flow for a local worker to
      pick up on demand or on a schedule.
    - ``run`` calls :func:`run_park_access_flow_once`, which executes the flow a
      single time in the current process using Prefect's ephemeral mode — no
      Prefect server or worker required.

!!! note
    All tunable values (the working spatial reference, walking distance, input and
    output paths) are read from ``config.yml`` via the ``config`` singleton rather
    than hardcoded, so the same flow runs unchanged across dev/test/prod.
"""

# ``from __future__ import annotations`` makes every type annotation in this module
# be treated as a lazily-evaluated string. This is the project standard and lets us
# use modern syntax (e.g. ``tuple[str, str]``) regardless of runtime quirks.
from __future__ import annotations

import importlib.util  # used to detect whether the package is importable without importing it
import os
import sys
from pathlib import Path  # project standard: always use pathlib.Path for filesystem paths

# Prefect's decorators: ``flow`` marks the top-level orchestration function and
# ``task`` marks each individually-tracked unit of work inside the flow.
from prefect import flow, task

# Project root directory: this file lives in ``<root>/scripts/``, so the project
# root is two levels up. Everything below is anchored to this path.
DIR_PRJ = Path(__file__).parent.parent

# The ``arcpy_orchestration`` package normally gets installed (``pip install -e .``)
# so it is importable directly. As a fallback (e.g. a fresh checkout that has not
# been installed yet), we add the ``src/`` directory to ``sys.path`` so the import
# below still succeeds. ``find_spec`` checks for importability without importing.
if importlib.util.find_spec("arcpy_orchestration") is None:
    src_dir = DIR_PRJ / "src"
    if not src_dir.exists():
        # No installed package and no source tree means we cannot continue.
        raise EnvironmentError("Unable to import arcpy_orchestration.")
    sys.path.insert(0, str(src_dir))

# These imports are placed after the sys.path manipulation above, hence the
# ``# noqa: E402`` markers telling the linter the "module-level import not at top
# of file" rule is intentionally relaxed here.
from arcpy_orchestration import park_access  # noqa: E402
from arcpy_orchestration.config import config  # noqa: E402
from arcpy_orchestration.orchestration import (  # noqa: E402
    build_prefect_environment,
    export_prefect_environment,
    render_effective_runtime_settings,
    resolve_prefect_runtime_config,
)

# --- Pipeline parameters (read once from configuration) ---------------------
# Pulling these from ``config`` keeps spatial references, distances, and field
# names out of the code itself and centralised in ``config.yml``.
WORKING_WKID: int = config.spatial.working_wkid  # projected CRS used for distance math
WALK_DISTANCE_M: float = config.park_access.walk_distance_m  # walking radius in metres
VALUE_FIELD: str = config.park_access.value_field  # parcel attribute to summarise

# --- Input / output dataset paths -------------------------------------------
# Each configured path is relative to the project root, so we join it onto
# ``DIR_PRJ`` and convert to ``str`` because arcpy expects string paths.
PARKS_FC: str = str(DIR_PRJ / config.park_access.parks_fc)  # source parks feature class
PARCELS_FC: str = str(DIR_PRJ / config.park_access.parcels_fc)  # source parcels feature class
OUTPUT_PARCELS_FC: str = str(DIR_PRJ / config.park_access.output_parcels_fc)  # result parcels
OUTPUT_SUMMARY_PATH: str = str(DIR_PRJ / config.park_access.output_summary_path)  # summary table

# --- Intermediate workspace -------------------------------------------------
# Reprojected inputs are written to a file geodatabase under ``data/interim``.
# These are throwaway intermediates regenerated on every run.
_INTERIM_GDB: str = str(DIR_PRJ / "data" / "interim" / "interim.gdb")
PARKS_PROJECTED_FC: str = f"{_INTERIM_GDB}/parks_projected"
PARCELS_PROJECTED_FC: str = f"{_INTERIM_GDB}/parcels_projected"

# --- Concurrency policy -----------------------------------------------------
# ArcPy is not safe to run concurrently against the same workspace, so we cap the
# flow to a single in-flight run. ``ENQUEUE`` means overlapping triggers wait in
# line rather than being dropped or run in parallel.
FLOW_CONCURRENCY_LIMIT = 1
FLOW_COLLISION_STRATEGY = "ENQUEUE"


@task
def project_inputs_task() -> tuple[str, str]:
    """Reproject the raw parks and parcels inputs into the working CRS.

    Distance and area calculations must be performed in a projected coordinate
    system, so this first task projects both source datasets to ``WORKING_WKID``
    before any measurement happens downstream.

    Returns:
        tuple[str, str]: Paths to the projected parks and parcels feature classes.
    """
    # Project each source feature class into the shared working CRS. The helper
    # writes to the interim geodatabase paths defined above and returns the path.
    parks = park_access.project_to_working_crs(PARKS_FC, PARKS_PROJECTED_FC, WORKING_WKID)
    parcels = park_access.project_to_working_crs(PARCELS_FC, PARCELS_PROJECTED_FC, WORKING_WKID)
    return parks, parcels


@task
def parcels_near_parks_task(parks_projected: str, parcels_projected: str) -> str:
    """Select the parcels that fall within walking distance of a park.

    Args:
        parks_projected: Path to the parks feature class in the working CRS.
        parcels_projected: Path to the parcels feature class in the working CRS.

    Returns:
        str: Path to the output feature class containing the nearby parcels.
    """
    # Delegate the spatial selection to the package; all tuning values come from
    # the module-level configuration constants.
    return park_access.parcels_within_walking_distance(
        parks_fc=parks_projected,
        parcels_fc=parcels_projected,
        out_fc=OUTPUT_PARCELS_FC,
        walk_distance_m=WALK_DISTANCE_M,
        working_wkid=WORKING_WKID,
    )


@task
def summarize_parcels_task(parcels_near_parks: str):
    """Summarise the selected parcels by the configured value field.

    Args:
        parcels_near_parks: Path to the parcels-near-parks feature class.

    Returns:
        The summary object produced by the package (e.g. a DataFrame/record set).
    """
    # Aggregate the nearby parcels on the configured value field.
    return park_access.summarize_parcels(
        parcels_fc=parcels_near_parks,
        value_field=VALUE_FIELD,
    )


@task
def export_summary_task(parcel_summary) -> str:
    """Write the parcel summary to its configured output location.

    Args:
        parcel_summary: The summary object returned by :func:`summarize_parcels_task`.

    Returns:
        str: Path to the written summary file.
    """
    # Persist the in-memory summary to disk at the configured output path.
    return park_access.export_summary(parcel_summary, OUTPUT_SUMMARY_PATH)


@flow(name="park-access-flow", persist_result=True, log_prints=True)
def park_access_flow() -> str:
    """Run the full park-access pipeline as a single Prefect flow.

    The flow chains the four tasks together; Prefect tracks each task run, so the
    UI shows per-step state, timing, and logs. ``persist_result=True`` stores the
    flow's return value and ``log_prints=True`` routes ``print`` output to the
    Prefect logs.

    Returns:
        str: Path to the exported summary file (the final pipeline output).
    """
    # 1. Reproject the inputs into the working CRS.
    parks_projected, parcels_projected = project_inputs_task()
    # 2. Select parcels within walking distance of a park.
    nearby_parcels = parcels_near_parks_task(parks_projected, parcels_projected)
    # 3. Summarise those parcels by the configured value field.
    parcel_summary = summarize_parcels_task(nearby_parcels)
    # 4. Export the summary and return its path as the flow result.
    return export_summary_task(parcel_summary)


def get_managed_flow_deployment_settings() -> dict[str, object]:
    """Return declarative deployment settings for no-concurrency local execution."""
    # Bundle the concurrency policy so it can be passed as keyword arguments to
    # ``flow.serve`` and reused/inspected elsewhere.
    return {
        "concurrency_limit": FLOW_CONCURRENCY_LIMIT,
        "collision_strategy": FLOW_COLLISION_STRATEGY,
    }


def serve_park_access_flow() -> None:
    """Resolve the runtime configuration and serve the flow for local execution.

    This is the entry point used when the module is executed as a script. It
    prepares the Prefect environment on disk, prints the effective settings for
    operator visibility, and then hands the flow to Prefect's ``serve`` loop so a
    local worker can run it on demand or on a schedule.
    """
    # Resolve the validated Prefect runtime configuration (paths, database URL, etc.).
    runtime_config = resolve_prefect_runtime_config()
    # Write the corresponding PREFECT_* environment file so the worker and server
    # share the same settings. ``overwrite=True`` keeps it in sync on every serve.
    export_prefect_environment(build_prefect_environment(runtime_config), overwrite=True)

    # Surface the effective settings on stdout so operators can confirm what is active.
    print(render_effective_runtime_settings(runtime_config))

    deployment_kwargs = get_managed_flow_deployment_settings()
    try:
        # Preferred path: serve with the full concurrency policy (limit + strategy).
        park_access_flow.serve(name="park-access", **deployment_kwargs)
    except TypeError:
        # Fallback for Prefect versions whose ``serve`` signature does not accept
        # ``collision_strategy``: still enforce the hard single-run limit.
        park_access_flow.serve(name="park-access", concurrency_limit=FLOW_CONCURRENCY_LIMIT)


def run_park_access_flow_once() -> str:
    """Execute the flow exactly once in-process, with no Prefect server required.

    This is the "singleton" execution path. A Prefect ``@flow`` is an ordinary
    callable, so invoking it runs the whole pipeline synchronously here and now.
    To avoid Prefect trying to reach the configured API server (which may not be
    running), this function clears ``PREFECT_API_URL`` for the current process so
    Prefect falls back to **ephemeral mode** — a temporary, in-process API backed
    by the local SQLite metadata database. No server and no worker are involved.

    !!! note
        Run state and results are still recorded in the project-local SQLite
        database and result storage, exactly as configured; only the long-running
        server/worker processes are skipped.

    Returns:
        str: Path to the exported summary file (the flow's return value).
    """
    # Resolve and apply the project-local Prefect paths/settings so the ephemeral
    # API uses the same SQLite database and result storage as the served version.
    runtime_config = resolve_prefect_runtime_config()
    export_prefect_environment(build_prefect_environment(runtime_config), overwrite=True)

    # Drop any configured API URL for this process. With no API URL set, Prefect 3
    # starts an ephemeral in-process API instead of trying to connect to a server.
    os.environ.pop("PREFECT_API_URL", None)
    # Belt-and-suspenders: explicitly allow ephemeral mode in case it was disabled.
    os.environ["PREFECT_SERVER_ALLOW_EPHEMERAL_MODE"] = "true"

    print(render_effective_runtime_settings(runtime_config))
    print("Running park-access flow once in ephemeral (serverless) mode...")

    # Calling the decorated flow runs it immediately and returns its result.
    return park_access_flow()


def main(argv: list[str] | None = None) -> None:
    """Dispatch between the ``serve`` and ``run`` execution modes.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``). The first
            argument selects the mode: ``serve`` (default) keeps the flow served
            for a worker, while ``run`` executes the flow a single time without a
            server.
    """
    args = sys.argv[1:] if argv is None else argv
    # Default to "serve" to preserve the previous behaviour when no command is given.
    command = args[0].lower() if args else "serve"

    if command == "run":
        run_park_access_flow_once()
    elif command == "serve":
        serve_park_access_flow()
    else:
        raise SystemExit(
            f"Unknown command: {command!r}. Use 'serve' (default) or 'run'."
        )


if __name__ == "__main__":
    # Entry point: choose the mode from the command line (defaults to 'serve').
    main()
