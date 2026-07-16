# Why Prefect Is the Orchestration Choice

This page explains why **Prefect** is the orchestration platform for this project — covering
the alternatives that were considered, the specific priorities this project must satisfy, and
how Prefect meets them.

## Choosing Prefect over the alternatives

Two platforms were the most obvious candidates alongside Prefect: Dagster and Apache Airflow.
Both were ruled out for reasons that are fundamental to this project's context, not just
superficial preference.

### Dagster — privatization risk

Dagster is technically capable, but its recent shift toward a privatized, commercially-controlled
model raised governance and sustainability concerns that we are not willing to accept.

Practically, this means:

- **Licensing and packaging uncertainty.** Future changes to what is open, what is gated, and
    how the project is distributed are now outside the community's control.
- **Roadmap dependency.** Feature direction and support priorities are increasingly determined
    by commercial incentives rather than open community consensus.
- **Migration cost risk.** If product boundaries continue to shift, teams that build deeply on
    Dagster may face forced migration work with little notice.

Prefect provides a comparable developer experience with a more stable, open governance posture
at the time this decision was made.

### Apache Airflow — too much for this scope

Airflow is the most widely deployed Python orchestrator in the industry and handles genuinely
complex, large-scale pipeline graphs well. For this project, however, the operational overhead
significantly outweighs the benefit.

The mismatch is structural:

- **Multi-component topology.** Airflow requires a webserver, a scheduler, a metadata database,
    and often a separate executor or message broker to be functional. Prefect's local setup is
    two processes — a server and a worker.
- **Higher operational surface.** Airflow upgrades, plugin management, secrets backends, and
    service configuration all require meaningful ongoing maintenance that is disproportionate
    to a single-host pipeline.
- **Conceptual overhead.** DAGs, operators, sensors, hooks, and XComs introduce a large
    abstraction layer for a workflow that is essentially a sequence of ArcPy steps.
- **Windows-first deployments are second-class.** Airflow is Linux-native; running it on the
    Windows host required by ArcGIS Pro adds friction at every layer.

Airflow would become relevant if this project grew into a large multi-team data platform with
dozens of interdependent pipelines shared across departments. At the current scope it is
simply more than needed.

## Project priorities

The choice of Prefect is not only about ruling out alternatives — it also reflects specific,
documented requirements for how this project must operate.

### Single-file, dual run-mode execution

A core project priority is that one flow definition supports both a
standalone one-off run and a fully served, web-managed deployment — with no separate "script
version" and "production version" to maintain. Prefect's `.serve()` model satisfies this
directly: `make data` runs the same file ephemerally, while `make prefect` serves it as a
persistent deployment.

### Windows-native ArcPy compatibility

This project must run on Windows against a full ArcGIS Pro installation to access `arcpy`
directly. The orchestrator must be lightweight enough to coexist cleanly in the Pro conda
environment and place no requirements on containerization or Linux-based execution.

### Lightweight setup

From the project README: setup is a standard editable install (`pip install -e .`) into a
cloned ArcGIS Pro conda environment. The orchestrator must not require a bespoke multi-step
bootstrap, a Docker build, or a separately provisioned server. Prefect starts from `pip` and
two commands.

### Configuration-driven, project-scoped runtime state

From the Speckit feature specification (`specs/001-prefect-orchestration-migration/spec.md`,
P1 and P2):

- All orchestration metadata and results must be stored under the repository directory
    (`prefect_home/`) — not in user-home defaults — so behavior is deterministic and
    portable across machines.
- All runtime properties (`PREFECT_HOME`, `PREFECT_API_DATABASE_CONNECTION_URL`,
    `PREFECT_LOCAL_STORAGE_PATH`, etc.) must be driven from `config/config.yml`, not from
    implicit Prefect defaults.

### Safe single-machine concurrency

Also from the Speckit spec (P1 acceptance criteria): on a single machine using SQLite as the
metadata store, the system must enforce a concurrency limit of one active run per managed flow,
with additional triggers queued rather than rejected. Prefect's deployment-level concurrency
controls handle this without external coordination infrastructure.

### Documentation-first operability

From the Speckit spec (P3): a new contributor must be able to complete local orchestration
setup and run a flow successfully using only repository documentation  without consulting 
any legacy guidance. A lower-complexity orchestrator directly supports this goal.

## Summary

| Criterion | Dagster | Apache Airflow | **Prefect** |
|---|---|---|---|
| Open governance | Uncertain (recently privatized) | Yes (Apache) | Yes |
| Local Windows setup | Moderate | Heavy (Linux-native) | **Lightweight** |
| Components to operate | Server + daemon | Webserver + scheduler + DB + executor | **Server + worker** |
| Dual run-mode (ephemeral + served) | Possible, complex | Not natural | **Native** |
| Config-driven runtime | Possible | Possible | **First-class** |
| SQLite single-run concurrency | Possible | Overkill | **Built-in** |

Prefect is not the right orchestrator for every team or every scale. It is the right choice
here because it satisfies all of this project's documented priorities without the governance
risk of Dagster or the operational overhead of Airflow.

## Review cadence

This decision will be revisited when any of the following occur:

- Material changes in Prefect licensing, support, or open-governance posture.
- Project growth that demands multi-team, multi-node scheduling beyond Prefect's local model.
- Significant changes in Dagster's governance or licensing that alter the current risk
    assessment.

Until then, Prefect remains the standard orchestration solution for this repository.