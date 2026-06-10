# Feature Specification: Prefect Orchestration Migration

**Feature Branch**: `[001-prefect-orchestration-migration]`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Replace, both in documentation and in the code, legacy orchestration with Prefect for orchestration. Create keys in the config for properties, and set at runtime following the general directions from this investigation with Copilot."

## Clarifications

### Session 2026-06-10

- Q: How should the system behave when a second run is triggered while one flow run is already active? → A: Queue the new run and start it automatically after the active run completes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Orchestration Locally with Project-Scoped State (Priority: P1)

As a developer running ArcPy orchestration locally, I can start and run workflows with Prefect while all orchestration state is contained within the repository so runs are deterministic and portable.

**Why this priority**: This is the core operational outcome of replacing legacy orchestration; without project-local state and runnable orchestration, migration value is not realized.

**Independent Test**: Can be fully tested by configuring the project, starting local orchestration services, triggering a sample flow run, and verifying orchestration metadata and persisted results are written under a repo-local Prefect directory.

**Acceptance Scenarios**:

1. **Given** a clean clone of the repository, **When** a developer applies documented runtime setup and starts local orchestration, **Then** orchestration metadata is persisted to a SQLite database under the project directory.
2. **Given** result persistence is enabled through project configuration, **When** a flow with return values runs successfully, **Then** persisted results are stored under a project-local storage path.
3. **Given** the project runs on a single machine with SQLite metadata storage, **When** any production project flow is defined, **Then** the flow enforces a concurrency limit of one active run.
4. **Given** an active flow run already exists, **When** a second run is triggered for the same managed flow, **Then** the second run is queued and starts only after the active run completes.

---

### User Story 2 - Configure Prefect Behavior Through Project Configuration (Priority: P2)

As a maintainer, I can manage Prefect runtime properties from project configuration so orchestration behavior is explicit, reproducible, and environment-aware without hidden global defaults.

**Why this priority**: Centralized configuration prevents drift and supports repeatable setup across developers and environments.

**Independent Test**: Can be fully tested by setting Prefect-related keys in project configuration, running bootstrap/setup logic, and confirming runtime environment values match configured settings.

**Acceptance Scenarios**:

1. **Given** Prefect configuration keys exist in project config, **When** runtime setup executes, **Then** runtime properties are exported or applied consistently from those keys.
2. **Given** an override is provided for one configured Prefect property, **When** setup executes, **Then** the runtime value reflects the override and does not silently fall back to unrelated defaults.

---

### User Story 3 - Use Updated Documentation for Migration and Daily Operations (Priority: P3)

As a team member, I can follow documentation that references Prefect instead of legacy orchestration so onboarding, local setup, and troubleshooting align with the current orchestration platform.

**Why this priority**: Accurate documentation reduces setup errors and support burden after the orchestration migration.

**Independent Test**: Can be fully tested by following only project documentation to perform first-time setup and execute a basic orchestration run without consulting legacy guidance.

**Acceptance Scenarios**:

1. **Given** current repository documentation, **When** a new contributor follows orchestration setup instructions, **Then** they can complete setup using Prefect-only terminology and steps.
2. **Given** all migration updates are complete, **When** searching project docs for orchestration guidance, **Then** no active legacy setup path remains for normal development workflows.

---

### Edge Cases

- How does setup behave when the project-local Prefect directory does not exist yet?
- How does runtime setup behave when one or more required Prefect configuration keys are missing or empty?
- What happens when stale legacy environment variables are still present in a developer shell?
- How does local orchestration behavior respond if the SQLite database file is locked or corrupted?
- What happens if a flow definition omits the required single-run concurrency guard?
- How does orchestration behave if a second run is triggered while one run is already active?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST replace legacy orchestration execution paths with Prefect-based orchestration execution paths for local development workflows.
- **FR-002**: The system MUST define project configuration keys for Prefect runtime properties, including project-local home directory, orchestration metadata database connection URL, local result storage path, result persistence default behavior, and local API URL.
- **FR-003**: The system MUST apply Prefect runtime properties from project configuration at runtime before local orchestration services and workers are started.
- **FR-004**: The system MUST ensure orchestration metadata persistence uses a project-local SQLite database path rather than a user-home default path.
- **FR-005**: The system MUST ensure flow/task result persistence is enabled by default for project workflows.
- **FR-006**: The system MUST persist flow/task results to a project-local storage directory.
- **FR-007**: The system MUST provide a reproducible project bootstrap path that initializes required Prefect runtime properties for local development.
- **FR-008**: The system MUST update repository documentation to remove legacy orchestration guidance and replace it with Prefect setup, execution, and troubleshooting guidance.
- **FR-009**: The system MUST preserve existing ArcPy workflow business behavior while changing orchestration tooling.
- **FR-010**: The system MUST provide clear error feedback when required Prefect runtime configuration cannot be resolved or applied.
- **FR-011**: The system MUST prohibit concurrent execution for project flows when using single-machine SQLite orchestration metadata.
- **FR-012**: The system MUST enforce a managed-flow concurrency limit of 1 through Prefect deployment or serve configuration using supported declarative concurrency controls equivalent to `concurrency_limit=1`.
- **FR-013**: The system MUST configure collision behavior so newly triggered runs queue when a managed flow already has an active run and start only after the active run completes, using FIFO queue ordering for runs of the same managed flow.
- **FR-014**: The system MUST detect SQLite metadata database lock or corruption conditions during orchestration startup and provide actionable recovery guidance.
- **FR-015**: The system MUST detect stale legacy-related environment variables during Prefect bootstrap and emit a warning with remediation steps.

### Key Entities *(include if feature involves data)*

- **Orchestration Runtime Configuration**: Project-defined settings that control orchestration behavior at runtime (home directory, metadata DB URL, result storage path, API URL, result persistence policy).
- **Orchestration Metadata Store**: Project-local SQLite database containing orchestration state such as flow runs, task runs, logs, deployments, and related operational records.
- **Result Storage Location**: Project-local file system directory used to persist serialized flow/task return values.
- **Bootstrap Context**: Runtime execution context that maps project configuration into active process environment before orchestration commands are launched.
- **Flow Concurrency Policy**: Project rule that limits each managed flow to a single active run in local SQLite mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of local orchestration runs in the default developer workflow write orchestration metadata to a database file located under the repository path.
- **SC-002**: At least 95% of successful flow runs that produce return values persist those values to the configured project-local result storage path.
- **SC-003**: A new contributor can complete local orchestration setup and execute one successful sample flow in under 20 minutes using repository documentation only.
- **SC-004**: Orchestration-related support questions caused by outdated legacy instructions are reduced by at least 80% within one release cycle after documentation migration.
- **SC-005**: Existing ArcPy workflow outputs for a representative smoke-run remain functionally equivalent before and after orchestration migration.
- **SC-006**: 100% of managed project flows are configured with an effective concurrency limit of one active run in local SQLite mode.

## Assumptions

- Existing ArcPy business logic remains valid and does not require domain-level refactoring for this migration.
- Local, single-node development execution is the primary target for this phase; horizontal multi-worker scaling is out of scope.
- Flow definitions in scope for this feature are Prefect-decorated Python flows where a concurrency limit can be explicitly configured.
- Project configuration loading infrastructure can be extended with additional orchestration keys without breaking current configuration access patterns.
- The team accepts project-local orchestration persistence as the default for development and testing environments.
- Existing scripts/entry points used for local orchestration can be updated to apply runtime properties before orchestration startup.

