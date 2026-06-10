# Quickstart: Validate Prefect Migration

## Goal

Validate that legacy orchestration has been replaced by Prefect for local orchestration, with project-local persistence, runtime-config-driven startup, and enforced single-run concurrency with queued follow-up runs.

## Prerequisites

- Windows machine with ArcGIS Pro Python environment available for this project.
- Project dependencies installed in active environment.
- Feature branch workspace checked out with migration changes.

## Scenario A: Runtime Configuration Bootstrap

1. Confirm project configuration includes required Prefect keys from the contract.
2. Run the project bootstrap/setup entrypoint for orchestration runtime.
3. Verify runtime environment values are set for:
    - `PREFECT_HOME`
    - `PREFECT_API_DATABASE_CONNECTION_URL`
    - `PREFECT_LOCAL_STORAGE_PATH`
    - `PREFECT_RESULTS_PERSIST_BY_DEFAULT`
    - `PREFECT_API_URL`
4. Expected outcome:
    - All required runtime properties are present and derived from project config values.

## Scenario B: Local Server and Metadata Persistence

1. Start local Prefect server using project bootstrap guidance.
2. Trigger one managed flow run.
3. Expected outcome:
    - Prefect metadata database file exists under project-local Prefect home path.
    - Run and log records are visible in Prefect UI/API for that run.

## Scenario C: Result Persistence Location

1. Execute a flow that returns a non-trivial value.
2. Expected outcome:
    - Persisted result record exists under configured local storage path.
    - Result persistence is enabled by default without per-run manual toggles.

## Scenario D: Concurrency Guard and Queue Behavior

1. Trigger run #1 for a managed flow.
2. While run #1 is active, trigger run #2 for the same managed flow.
3. Expected outcome:
    - Run #2 does not start immediately.
    - Run #2 enters queued/waiting-for-slot behavior.
    - Run #2 starts automatically after run #1 reaches a terminal state.

## Scenario E: Documentation Migration Check

1. Follow repository docs for orchestration setup and run instructions from scratch.
2. Expected outcome:
    - Steps are Prefect-based and executable.
    - legacy orchestration-first setup path is not presented as the active workflow.

## Scenario F: SQLite Lock/Corruption Recovery Path

1. Simulate or reproduce a metadata DB startup failure caused by lock or corruption.
2. Run the bootstrap or startup entrypoint.
3. Expected outcome:
    - Startup fails fast with a clear message.
    - Recovery guidance identifies the failing DB path and next recovery actions.

## Scenario G: Stale legacy orchestration Environment Detection

1. Set one or more legacy legacy orchestration environment variables in the shell.
2. Run the Prefect bootstrap entrypoint.
3. Expected outcome:
    - Bootstrap emits a warning identifying stale legacy orchestration-related variables.
    - Warning includes remediation guidance to remove or ignore deprecated variables.

## Scenario H: SC-005 ArcPy Output Equivalence Check

1. Prepare a representative baseline dataset and run the pre-migration workflow once to capture:
    - Output schema for parcels-near-parks feature class
    - Output row count
    - Summary metrics (`parcel_count`, `total_value`, `mean_value`)
2. Run the Prefect-managed migration flow using the same baseline dataset.
3. Compare pre/post outputs with the following pass criteria:
    - Schema fields and field types are equivalent
    - Row count is identical
    - Summary metrics are equal (or within documented floating-point tolerance)
4. Record pass/fail results in implementation notes with links to generated outputs.
5. Expected outcome:
    - Prefect migration preserves ArcPy business behavior for representative smoke-run outputs.

## References

- Spec: `spec.md`
- Research decisions: `research.md`
- Data model: `data-model.md`
- Runtime contract: `contracts/prefect-runtime-contract.md`

## Validation Sweep Notes (2026-06-10)

Executed checks in `./env`:

1. Scenario A: `setup_prefect.ps1 -Action show-config` confirms resolved `PREFECT_*` values from project config.
2. Scenario G: stale `LEGACY_HOME` and `LEGACY_*` variables trigger warning output in bootstrap diagnostics.
3. Scenario F: synthetic corrupted SQLite file triggers actionable recovery guidance from `assert_sqlite_health`.

Actionable follow-up for full end-to-end sweep:

1. Run Scenarios B, C, and D with local Prefect server/worker/serve processes active and representative ArcPy input data available.
2. Capture run IDs and output artifact paths for metadata/result persistence verification.
3. Execute Scenario H equivalence comparison against a saved pre-migration baseline dataset and attach comparison evidence to implementation notes.

