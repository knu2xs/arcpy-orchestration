# Tasks: Prefect Orchestration Migration

**Input**: Design documents from `/specs/001-prefect-orchestration-migration/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No standalone test tasks are included because tests were not explicitly requested in the
feature specification. Validation is performed through quickstart scenarios and implementation checkpoints.

**Organization**: Tasks are grouped by user story to enable independent implementation and validation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare project structure and dependencies for Prefect migration work.

- [X] T001 Add Prefect dependency to project runtime dependencies in pyproject.toml
- [X] T002 Create orchestration package namespace in src/arcpy_orchestration/orchestration/__init__.py
- [X] T003 [P] Create Prefect flow entrypoint scaffold in scripts/prefect_definitions.py
- [X] T004 [P] Create Prefect setup/bootstrap script scaffold in scripts/setup_prefect.ps1

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build core runtime/configuration infrastructure that all user stories depend on.

**⚠️ CRITICAL**: No user story work starts until this phase is complete.

- [X] T005 Add Prefect runtime configuration keys under environments.default in config/config.yml
- [X] T006 Implement Prefect runtime config resolver and typed mapping in src/arcpy_orchestration/orchestration/prefect_runtime.py
- [X] T007 Implement fail-fast required-key validation and error messages in src/arcpy_orchestration/orchestration/prefect_runtime.py
- [X] T008 [P] Implement runtime environment export helper for PREFECT_* values in src/arcpy_orchestration/orchestration/prefect_env.py
- [X] T009 Wire setup_prefect bootstrap flow to resolver/export helpers in scripts/setup_prefect.ps1
- [X] T010 Add shared orchestration logging bootstrap helper in src/arcpy_orchestration/orchestration/prefect_logging.py

**Checkpoint**: Foundation complete. User story delivery can now proceed.

---

## Phase 3: User Story 1 - Run Orchestration Locally with Project-Scoped State (Priority: P1) 🎯 MVP

**Goal**: Deliver runnable Prefect orchestration with project-local state, SQLite metadata persistence,
result persistence, and enforced single-active-run queue behavior.

**Independent Test**: Start Prefect locally via project scripts, trigger two runs of the same managed flow,
verify metadata/result persistence under project-local paths, and confirm run #2 waits then starts after run #1.

- [X] T011 [US1] Implement Prefect flow wrapping the existing park access pipeline in scripts/prefect_definitions.py
- [X] T012 [US1] Configure managed flow concurrency policy (limit=1, queue collision behavior) in scripts/prefect_definitions.py
- [X] T013 [US1] Configure project-local SQLite metadata DB URL and local storage path consumption in scripts/prefect_definitions.py
- [X] T014 [US1] Implement local Prefect server startup command path using bootstrap exports in scripts/setup_prefect.ps1
- [X] T015 [US1] Implement local Prefect worker startup command path using bootstrap exports in scripts/setup_prefect.ps1
- [X] T016 [P] [US1] Add queue-behavior verification utility for overlapping triggers in scripts/verify_prefect_queue.ps1
- [X] T017 [US1] Add smoke-run command wrapper for local orchestration validation in scripts/run_prefect_smoke.ps1
- [X] T035 [US1] Implement startup detection and actionable error path for SQLite lock/corruption in scripts/setup_prefect.ps1

**Checkpoint**: User Story 1 is functional and can be validated independently.

---

## Phase 4: User Story 2 - Configure Prefect Behavior Through Project Configuration (Priority: P2)

**Goal**: Ensure Prefect runtime behavior is fully controlled by project configuration with explicit
validation, precedence handling, and troubleshooting visibility.

**Independent Test**: Change Prefect values in project config, run bootstrap, and verify effective
runtime exports update accordingly; provide an invalid/missing key and confirm clear fail-fast errors.

- [X] T018 [US2] Add runtime settings accessor integration for Prefect config in src/arcpy_orchestration/config.py
- [X] T019 [US2] Implement path normalization and repository-local boundary validation in src/arcpy_orchestration/orchestration/prefect_runtime.py
- [X] T020 [US2] Implement effective-value rendering for bootstrap diagnostics in src/arcpy_orchestration/orchestration/prefect_runtime.py
- [X] T021 [US2] Wire setup script to print effective Prefect runtime settings before startup in scripts/setup_prefect.ps1
- [X] T022 [P] [US2] Create troubleshooting helper to display resolved PREFECT_* values in scripts/show_prefect_runtime.ps1
- [X] T023 [US2] Enforce result persistence default application during orchestration startup in scripts/setup_prefect.ps1
- [X] T024 [US2] Add missing/invalid config failure path handling for setup commands in scripts/setup_prefect.ps1
- [X] T037 [US2] Implement stale legacy environment variable detection and warning output in scripts/setup_prefect.ps1

**Checkpoint**: User Story 2 is functional and can be validated independently.

---

## Phase 5: User Story 3 - Use Updated Documentation for Migration and Daily Operations (Priority: P3)

**Goal**: Replace legacy orchestration documentation with Prefect-first onboarding, setup, and operations guidance.

**Independent Test**: Follow documentation only to perform first-time local setup and execute a basic
Prefect run without consulting legacy orchestration instructions.

- [X] T025 [US3] Replace legacy orchestration overview and setup references with Prefect guidance in README.md
- [X] T026 [P] [US3] Update setup documentation to Prefect server/worker/bootstrap workflow in docsrc/mkdocs/setup.md
- [X] T027 [P] [US3] Update architecture rationale from legacy orchestration to Prefect in docsrc/mkdocs/why_this_approach.md
- [X] T028 [US3] Update API/documentation references to Prefect orchestration entrypoints in docsrc/mkdocs/api.md
- [X] T029 [US3] Add migration/deprecation note for legacy orchestration scripts in README.md
- [X] T036 [US3] Document SQLite lock/corruption recovery procedure in README.md and docsrc/mkdocs/setup.md
- [X] T038 [US3] Add migration note documenting legacy variable cleanup in README.md

**Checkpoint**: User Story 3 is functional and can be validated independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, cleanup, and cross-story validation.

- [X] T030 [P] Remove legacy orchestration-specific implementation paths
- [X] T031 [P] Remove legacy orchestration setup entrypoints and point to Prefect workflow
- [X] T032 Align repository-level setup docs with Prefect migration outcomes in docsrc/mkdocs/index.md
- [X] T033 Run quickstart scenario validation sweep and perform SC-005 equivalence validation using a defined baseline dataset, schema check, row-count comparison, and summary-metric comparison; update actionable steps in specs/001-prefect-orchestration-migration/quickstart.md
- [X] T034 Update implementation evidence notes in specs/001-prefect-orchestration-migration/checklists/orchestration.md

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): No dependencies.
- Foundational (Phase 2): Depends on Setup completion; blocks all user stories.
- User Stories (Phases 3-5): Depend on Foundational completion.
- Polish (Phase 6): Depends on completion of selected user stories.

### User Story Dependencies

- User Story 1 (P1): Starts after Foundational; no dependency on US2/US3.
- User Story 2 (P2): Starts after Foundational; can proceed independently of US1 completion.
- User Story 3 (P3): Starts after Foundational; can proceed independently of US1/US2 completion.

### Preferred Completion Order

1. US1 for MVP orchestration value.
2. US2 for robust config/runtime management.
3. US3 for onboarding and operational documentation alignment.

---

## Parallel Execution Examples

### User Story 1

- T016 in scripts/verify_prefect_queue.ps1 can run in parallel with T014-T015 after T011-T013 are in place.

### User Story 2

- T022 in scripts/show_prefect_runtime.ps1 can run in parallel with T021 after T018-T020 exist.

### User Story 3

- T026 in docsrc/mkdocs/setup.md and T027 in docsrc/mkdocs/why_this_approach.md can run in parallel.

### Cross-Story

- US3 documentation tasks can run in parallel with US2 implementation after foundational completion; sequencing can be adjusted for team preference.

---

## Implementation Strategy

### MVP First (US1)

1. Complete Phases 1-2.
2. Complete Phase 3 (US1).
3. Validate independent test criteria for US1 before expanding scope.

### Incremental Delivery

1. Deliver US1 (runnable Prefect orchestration with queue-concurrency policy).
2. Deliver US2 (config-driven runtime robustness and diagnostics).
3. Deliver US3 (documentation migration and onboarding reliability).
4. Finish with Phase 6 cleanup and cross-cutting validation.

### Team Parallelization Strategy

1. Team completes Setup + Foundational together.
2. Developer A focuses on US1 execution path.
3. Developer B focuses on US2 runtime/config path.
4. Developer C focuses on US3 docs migration.
5. Rejoin for Phase 6 cleanup and final validation.

