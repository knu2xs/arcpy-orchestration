# arcpy-orchestration Constitution

## Core Principles

### I. Configuration First

- Runtime and orchestration behavior MUST be configured through project configuration and environment mapping.
- Implementation MUST NOT hardcode orchestration paths, API URLs, or concurrency policy values when a project config key exists.

### II. Local Persistence Boundary

- Local orchestration mode MUST persist Prefect home, metadata DB, and result storage inside repository-local paths.
- Any fallback to user-home defaults in local mode MUST be treated as a configuration failure.

### III. Deterministic Orchestration Safety

- In single-machine SQLite mode, managed flows MUST enforce one active run at a time.
- When a second run is triggered while one is active, the new run MUST queue and start automatically after completion of the active run.

### IV. Documentation Integrity

- Active setup and operations documentation MUST describe the current orchestration platform and commands.
- Deprecated orchestration paths MAY be mentioned only as migration notes and MUST NOT be presented as primary workflow.

### V. Validation Gate Before Implementation

- Feature implementation readiness MUST be demonstrated by complete spec, plan, and tasks artifacts aligned to this constitution.
- Quickstart validation scenarios MUST be executable and mapped to requirement outcomes before implementation is considered complete.

## Additional Constraints

- Primary platform target is Windows with ArcGIS Pro-compatible Python.
- Single-machine SQLite mode is valid for local and dev workflows; multi-node scaling is out of scope unless explicitly planned.

## Workflow and Quality Gates

- All feature tasks MUST map back to requirements or explicit process gates.
- Any ambiguity between spec wording and supported platform behavior MUST be resolved in spec text before implementation starts.
- Breaking changes to public workflow commands or docs MUST include migration guidance.

## Governance

- This constitution supersedes feature-level preferences where conflicts occur.
- Amendments require explicit update of this file and downstream artifact re-validation.
- Every analysis pass MUST report constitution violations as critical.

**Version**: 1.0.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10
