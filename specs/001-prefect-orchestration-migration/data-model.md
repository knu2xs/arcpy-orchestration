# Data Model: Prefect Orchestration Migration

## Entity 1: PrefectRuntimeConfig

- Purpose: Canonical project configuration values used to construct Prefect runtime properties.
- Source: `config/config.yml` environment blocks.
- Fields:
    - `home_path` (string, required): Project-local Prefect home directory.
    - `api_database_connection_url` (string, required): SQLAlchemy async URL for metadata DB.
    - `local_storage_path` (string, required): Local filesystem location for persisted results.
    - `results_persist_by_default` (boolean, required): Default result persistence policy.
    - `api_url` (string, required): Prefect API endpoint URL for local server.
    - `worker_type` (string, optional): Worker execution type (for this feature, expected `process`).
    - `work_pool_name` (string, optional): Default local work pool name.
- Validation rules:
    - Paths must resolve under repository root for local mode.
    - `api_database_connection_url` must use async driver and point to local SQLite in this phase.
    - `api_url` must be a valid HTTP URL.

## Entity 2: PrefectRuntimeEnvironment

- Purpose: Runtime-resolved environment values exported before orchestration startup.
- Fields:
    - `PREFECT_HOME` (string)
    - `PREFECT_API_DATABASE_CONNECTION_URL` (string)
    - `PREFECT_LOCAL_STORAGE_PATH` (string)
    - `PREFECT_RESULTS_PERSIST_BY_DEFAULT` (string/boolean)
    - `PREFECT_API_URL` (string)
- Relationships:
    - Derived from `PrefectRuntimeConfig` by bootstrap mapping rules.
- Validation rules:
    - Required keys cannot be null or empty.
    - Exported values must match configured values after resolution.

## Entity 3: FlowConcurrencyPolicy

- Purpose: Declares no-concurrency execution policy for managed flows in single-machine SQLite mode.
- Fields:
    - `flow_name` (string, required)
    - `concurrency_limit` (integer, required; fixed to `1`)
    - `collision_strategy` (enum, required; `ENQUEUE` for this feature)
    - `scope` (enum, required; `managed_flow`)
- Relationships:
    - Applied to flow deployment/serve configuration.
- Validation rules:
    - `concurrency_limit` must equal `1`.
    - `collision_strategy` must enforce queued follow-up runs.

## Entity 4: OrchestrationMetadataStore

- Purpose: Persists orchestration state for observability and control.
- Backing store: SQLite database under project-local Prefect home.
- Conceptual records:
    - Flow runs
    - Task runs
    - Run logs
    - Deployments
    - Concurrency lease/slot state
    - Artifacts/variables (as managed by Prefect)
- Validation rules:
    - DB file path remains project-local in default workflow.

## Entity 5: QueuedRunLifecycle

- Purpose: Describes expected state progression when concurrency slot is unavailable.
- Fields:
    - `run_id` (string)
    - `deployment_or_flow_key` (string)
    - `state` (enum)
    - `queued_at` (datetime)
    - `started_at` (datetime, nullable)
    - `finished_at` (datetime, nullable)
- State transitions:
    - `Scheduled/Pending` -> `AwaitingConcurrencySlot` -> `Running` -> `Completed|Failed|Cancelled|Crashed`
- Validation rules:
    - No second run may enter `Running` while another run for same managed flow is `Running`.

## Relationships Summary

- `PrefectRuntimeConfig` -> materializes -> `PrefectRuntimeEnvironment`
- `PrefectRuntimeEnvironment` -> configures -> `OrchestrationMetadataStore`
- `FlowConcurrencyPolicy` -> governs -> `QueuedRunLifecycle`
- `OrchestrationMetadataStore` -> records -> runtime and lifecycle state transitions

