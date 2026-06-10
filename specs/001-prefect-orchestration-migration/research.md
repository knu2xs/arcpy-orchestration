# Research: Prefect Orchestration Migration

## Decision 1: Use project-local Prefect home and explicit local persistence paths

- Decision: Configure and apply project-local Prefect runtime settings for `PREFECT_HOME`, `PREFECT_API_DATABASE_CONNECTION_URL`, `PREFECT_LOCAL_STORAGE_PATH`, and `PREFECT_API_URL`.
- Rationale: This reproduces legacy orchestration-style local state containment, prevents accidental writes to user-home defaults, and supports deterministic onboarding.
- Alternatives considered:
    - Rely on Prefect defaults in `~/.prefect`: rejected because state escapes repository boundaries.
    - Configure only `PREFECT_HOME`: rejected because explicit DB and storage URL/path pinning is clearer and safer.

## Decision 2: Enable result persistence globally for this project profile

- Decision: Set `PREFECT_RESULTS_PERSIST_BY_DEFAULT=true` for the project runtime profile/bootstrap.
- Rationale: Prefect does not persist results by default; migration requirements require persisted flow/task return values in repo-local storage.
- Alternatives considered:
    - Enable persistence per flow/task only: rejected because coverage is easy to miss and violates consistency goals.
    - Do not persist results globally: rejected because it conflicts with FR-005/FR-006 outcomes.

## Decision 3: Keep SQLite as the orchestration metadata backend for this phase

- Decision: Use SQLite (`sqlite+aiosqlite`) under project-local Prefect home for local single-machine execution.
- Rationale: This phase explicitly targets single-node local development with no horizontal scaling; SQLite minimizes setup burden.
- Alternatives considered:
    - PostgreSQL now: rejected as unnecessary complexity for current scope.
    - Prefect Cloud only: rejected because requirement calls for fully self-contained local repository operation.

## Decision 4: Enforce single active run with queued follow-up runs

- Decision: Enforce effective concurrency limit of 1 with queue-on-collision behavior for managed flows.
- Rationale: This satisfies clarified behavior: no concurrent execution, while second runs wait and start after active run completion.
- Alternatives considered:
    - Reject new runs when at limit: rejected because user selected queue behavior.
    - Cancel running run and start latest: rejected because this risks partial ArcPy processing side effects.

## Decision 5: Implement concurrency limit via Prefect deployment/serve configuration

- Decision: Apply the flow concurrency guard through Prefect declarative deployment/serve concurrency controls (`concurrency_limit=1`) with queue semantics.
- Rationale: Prefect documents concurrency limit on deployment/serve paths; this is the supported mechanism to achieve the specified policy.
- Alternatives considered:
    - Decorator-only concurrency parameter: treated as non-portable/uncertain in current Prefect API docs; use equivalent declarative mechanism already allowed by FR-012.
    - Runner process-limit alone: rejected because process limits do not define per-flow concurrency policy.

## Decision 6: Add first-class configuration keys under project config

- Decision: Add a dedicated Prefect configuration section in `config/config.yml` environment defaults and read values via existing config singleton at runtime.
- Rationale: This aligns with project configuration conventions and keeps orchestration behavior centralized and environment-aware.
- Alternatives considered:
    - Hardcode values in scripts: rejected due to maintainability and environment drift.
    - Depend only on `.env`: rejected because project standard centers on `config.yml` as source of truth.

## Decision 7: Replace legacy orchestration docs and entrypoint guidance with Prefect equivalents

- Decision: Update README/docs/scripts references from legacy orchestration webserver/daemon patterns to Prefect server/worker/work-pool patterns.
- Rationale: Documentation consistency is required for onboarding and success criteria.
- Alternatives considered:
    - Keep dual legacy orchestration/Prefect guidance: rejected for this migration feature because it creates ambiguity and support overhead.

## Consequences and follow-on notes

- SQLite remains dev/single-machine scoped; future scale-up should plan migration to PostgreSQL.
- ArcPy output persistence remains controlled by project code paths and geodatabases, distinct from Prefect result persistence.
- Runtime bootstrap order is critical: configuration must be applied before server/worker/flow startup.

