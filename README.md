# ArcPy Orchestration

Web-based orchestration for ArcPy workflows using Prefect on a single Windows host with ArcGIS Pro.

## Executive Summary

This repository demonstrates how to run ArcPy production workflows with:

- Prefect for orchestration (local server, worker, deployment-style flow serving)
- Project-local runtime state (`prefect_home/`) for reproducible local behavior
- Configuration-driven runtime properties resolved from `config/config.yml`
- Deterministic single-machine execution (`concurrency_limit=1` for managed flows)

The sample pipeline identifies parcels within walking distance of parks, then exports a summary workbook.

## Quick Start

1. Configure Prefect runtime keys in `config/config.yml` under `environments.default.orchestration.prefect`.
2. Bootstrap environment variables:

```powershell
.\scripts\setup_prefect.ps1 -Action bootstrap
```

3. Start local Prefect server:

```powershell
.\scripts\setup_prefect.ps1 -Action start-server
```

4. Start local worker (separate shell):

```powershell
.\scripts\setup_prefect.ps1 -Action start-worker
```

5. Serve managed flow deployment settings (`concurrency_limit=1`):

```powershell
.\scripts\setup_prefect.ps1 -Action serve-flow
```

6. Execute a smoke run:

```powershell
.\scripts\run_prefect_smoke.ps1
```

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
