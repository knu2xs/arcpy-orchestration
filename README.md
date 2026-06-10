# ArcPy Orchestration

Orchestration for ArcPy workflows using Prefect on a single Windows host with ArcGIS Pro — runnable
both as a standalone script and as a web-based, scheduled, monitored flow.

## Executive Summary

This repository demonstrates how to run ArcPy production workflows with:

- Prefect for orchestration (local server, worker, deployment-style flow serving)
- Project-local runtime state (`prefect_home/`) for reproducible local behavior
- Configuration-driven runtime properties resolved from `config/config.yml`
- Deterministic single-machine execution (`concurrency_limit=1` for managed flows)

The sample pipeline identifies parcels within walking distance of parks, then exports a summary workbook.

## Project Priorities

These three priorities drive every design decision in this project:

- **One orchestration file, two run modes.** A single flow definition
  ([scripts/make_data_prefect.py](scripts/make_data_prefect.py)) serves *both* a standalone
  "singleton" run and full web-based orchestration. Run it directly with no server
  (`make data`) for a one-off, in-process execution, or serve the *same* file
  (`make prefect`) so it can be scheduled, triggered, and monitored from the Prefect UI.
  There is no separate "script version" and "production version" to keep in sync.

- **Windows-native for first-class ArcPy access.** The project targets Windows so it can use the
  ArcGIS Pro `arcpy` library directly for geoprocessing analysis. The flow runs in an ArcGIS
  Pro-compatible Python environment, so the existing ArcPy business logic runs unchanged — no
  containers, remote geoprocessing services, or cross-platform shims required.

- **`pip`-installable, no heavy install workflow.** The package installs with a standard editable
  install (`pip install -e .`) into a cloned ArcGIS Pro conda environment. There is no bespoke
  multi-step bootstrap, no Docker image to build, and no separate orchestration server to provision
  — keeping setup light and approachable.

## Quick Start

### Run it once, no server (singleton)

The fastest path: execute the pipeline a single time in the current process using Prefect's
ephemeral mode. No Prefect server or worker is required.

```powershell
.\make.ps1 data
```

### Run it as a web-based, scheduled flow

For the full web-UI experience from a single call, run:

```powershell
.\make.ps1 prefect
```

With no action specified, `make prefect` defaults to `start-all`: it launches the Prefect
**server** and a **worker** in their own windows, then **serves** the managed flow
(`concurrency_limit=1`) in the current window. The Prefect UI is hosted by the server window
(default <http://127.0.0.1:4200>). Configure the runtime keys in `config/config.yml` under
`environments.default.orchestration.prefect` before the first run.

Once everything is up, execute a smoke run:

```powershell
.\scripts\run_prefect_smoke.ps1
```

If you prefer to manage each process yourself (or are running on a remote/headless host where the
server, worker, and flow belong in separate, individually-controlled processes), run the actions
individually in separate shells:

```powershell
.\make.ps1 prefect start-server     # hosts the Prefect UI
.\make.ps1 prefect start-worker     # picks up scheduled/triggered runs
.\make.ps1 prefect serve-flow       # serves the managed flow deployment
```

!!! note
    `make.cmd` exposes the same target for classic Command Prompt usage, e.g. `make prefect` or
    `make prefect start-server`. Both entry points delegate to `scripts\setup_prefect.ps1` inside
    the project conda environment.

!!! tip "Doing more than testing?"
    The `make prefect` workflow above is intended for local development and evaluation. For a
    production deployment — running Prefect as a managed Windows service behind IIS with HTTPS —
    follow the full setup guide in [docsrc/mkdocs/setup.md](docsrc/mkdocs/setup.md) instead.

## Runtime Configuration Keys

Configured under `orchestration.prefect`:

- `home_path`
- `api_database_connection_url`
- `local_storage_path`
- `results_persist_by_default`
- `api_url`
- `worker_type`
- `work_pool_name`

At bootstrap, these map to:

- `PREFECT_HOME`
- `PREFECT_API_DATABASE_CONNECTION_URL`
- `PREFECT_LOCAL_STORAGE_PATH`
- `PREFECT_RESULTS_PERSIST_BY_DEFAULT`
- `PREFECT_API_URL`

## Troubleshooting

### SQLite lock/corruption startup failures

If bootstrap fails with a SQLite lock/corruption error:

1. Stop all local Prefect processes (server, workers, and flow serve processes).
2. Back up `prefect_home/prefect.db`.
3. If lock-related, retry after processes are stopped.
4. If corruption-related, replace the DB with a clean file and restart bootstrap.

For implementation details and rationale, see documentation in `docsrc/mkdocs/`.
