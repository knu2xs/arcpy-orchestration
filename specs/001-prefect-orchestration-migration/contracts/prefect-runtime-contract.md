# Contract: Prefect Runtime and Concurrency

## 1. Configuration Contract

The project configuration MUST provide Prefect keys that can be resolved at runtime for local orchestration.

### Required keys

- `orchestration.prefect.home_path` (string)
- `orchestration.prefect.api_database_connection_url` (string)
- `orchestration.prefect.local_storage_path` (string)
- `orchestration.prefect.results_persist_by_default` (boolean)
- `orchestration.prefect.api_url` (string)

### Required behavior

- Bootstrap logic MUST fail fast with a clear error when any required key is missing or empty.
- Runtime-exported values MUST be derived from configuration, not hardcoded constants.
- Default local values MUST resolve to repository-local paths for this feature.

## 2. Environment Mapping Contract

Before starting Prefect server, worker, or flow execution entrypoints, the runtime MUST set:

- `PREFECT_HOME` <- `orchestration.prefect.home_path`
- `PREFECT_API_DATABASE_CONNECTION_URL` <- `orchestration.prefect.api_database_connection_url`
- `PREFECT_LOCAL_STORAGE_PATH` <- `orchestration.prefect.local_storage_path`
- `PREFECT_RESULTS_PERSIST_BY_DEFAULT` <- `orchestration.prefect.results_persist_by_default`
- `PREFECT_API_URL` <- `orchestration.prefect.api_url`

## 3. Concurrency Contract

For each managed project flow in this feature scope:

- Effective concurrency limit MUST be `1` active run.
- If a run is triggered while one run is active, the new run MUST be queued and started automatically after the active run completes.
- Concurrent active runs for the same managed flow are prohibited in local SQLite mode.

## 4. Documentation Contract

- User-facing setup and operations documentation MUST present Prefect as the orchestration platform.
- legacy orchestration-specific setup instructions MUST be removed or explicitly deprecated for this feature path.

## 5. Validation Contract

A feature validation run is compliant only if all of the following are true:

- Metadata DB is created/used under project-local Prefect home.
- Persisted results are written under configured local storage path.
- Attempted overlapping triggers do not execute concurrently and instead follow queue behavior.
- Runtime environment values observed during startup match configured key values.

