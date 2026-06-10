# Implementation Plan: Prefect Orchestration Migration

**Branch**: `[main]` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-prefect-orchestration-migration/spec.md`

## Summary

Migrate orchestration from legacy orchestration to Prefect while preserving ArcPy workflow behavior.
The implementation will centralize Prefect runtime properties in project config, apply them
at runtime before orchestration startup, enforce a single active managed-flow run with queued
follow-up runs, and update documentation to Prefect-first guidance.

## Technical Context

**Language/Version**: Python >=3.9 (project requirement), running in ArcGIS Pro-compatible environment

**Primary Dependencies**:

- `prefect` (new orchestration runtime)
- Existing project package `arcpy_orchestration`
- `arcpy` (ArcGIS Pro-provided runtime dependency)
- Existing project dependency `openpyxl`

**Storage**:

- Prefect metadata DB: project-local SQLite (`sqlite+aiosqlite` URL)
- Prefect results: project-local filesystem storage under Prefect home
- Existing ArcPy outputs: geodatabases and Excel outputs as currently configured

**Testing**:

- Scenario-driven validation via quickstart scenarios (server, worker, run, queue behavior)
- Existing `pytest` suite in `testing/` remains available for targeted additions when implementation tasks explicitly require test automation

**Target Platform**: Windows workstation/server environments with ArcGIS Pro installed

**Project Type**: Single Python package + scripts + documentation project

**Performance Goals**:

- Deterministic local startup for orchestration services
- Zero concurrent active runs per managed flow in local SQLite mode
- Queued follow-up run starts after active run completes

**Constraints**:

- Single-machine execution scope for this feature
- SQLite persistence model (no multi-node HA guarantees)
- Runtime settings must be config-driven and applied pre-startup
- Documentation must replace legacy orchestration-first guidance with Prefect-first guidance

**Scale/Scope**:

- Current scope: migrate existing pipeline orchestration path and docs
- Immediate target: local/dev workflows and maintainers
- Out of scope: horizontal scaling and production HA topology

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Constitution file at `.specify/memory/constitution.md` is ratified with enforceable MUST-level principles.
- Gate result (pre-research): PASS (plan scope aligns with configuration-first, local persistence, deterministic safety, and documentation integrity principles).
- Post-design re-check: PASS (design artifacts remain aligned; no constitution violations require justification).

## Project Structure

### Documentation (this feature)

```text
specs/001-prefect-orchestration-migration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── prefect-runtime-contract.md
└── tasks.md                # generated in /speckit.tasks phase
```

### Source Code (repository root)

```text
config/
├── config.yml

scripts/
├── legacy_orchestration_definitions.py          # to be replaced/migrated to Prefect entrypoint(s)
└── setup_legacy_orchestration.ps1               # to be replaced/migrated to Prefect setup path

src/
└── arcpy_orchestration/
    ├── config.py
    ├── park_access.py
    └── utils/

testing/
├── conftest.py
└── test_arcpy_orchestration.py

docsrc/
└── mkdocs/
```

**Structure Decision**: Keep the existing single-project Python structure and migrate orchestration
integration points in-place (config, scripts, docs) rather than introducing new top-level services.

## Complexity Tracking

No constitution violations identified that require justification.

