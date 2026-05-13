# Why Not ArcGIS Notebooks?

ArcGIS Notebook Server is an excellent platform for exploratory analysis,
sharing analytical narratives, and lightweight scheduled work. It is **not**
always the right host for production scheduled geoprocessing. This document
explains the trade-offs and why this project hosts scheduled ArcPy work in
ArcGIS Pro's Python environment behind a web UI (Plombery or Dagster)
instead.

## Quick comparison

| Concern | ArcGIS Notebook Server | This project (ArcGIS Pro + Plombery / Dagster + Servy) |
|---|---|---|
| Python runtime | Curated Notebook runtime image (`standard` / `advanced`) | Full ArcGIS Pro conda env (any package the Pro env supports) |
| ArcPy surface | Notebook runtime — subset of toolboxes and extensions | Full Pro install — every licensed extension and toolbox |
| Identity for downstream resources | Notebook Server service account or named-user token | Any Windows account, including a domain service account with Kerberos delegation |
| File-system access | Container-mounted volumes only | Any local disk, mapped drive, or UNC path the Windows account can reach |
| Database authentication | Stored credentials or username/password | OS authentication (Integrated Security) inherits the service account |
| Hardware | Docker container with CPU/RAM quotas, no GPU passthrough by default | Full host hardware — CPU, RAM, GPU, local SSD |
| Licensing | Notebook Server license on top of ArcGIS Enterprise | One ArcGIS Pro license per host |
| Code organization | Cells in `.ipynb` files | Plain `.py` modules in an importable package |
| Diff / review in Git | Notebook JSON noise, output churn | Standard Python diffs |
| Scheduling fidelity | Cron-style; one schedule per notebook | Multiple triggers per pipeline, manual runs, per-run parameters |
| Per-run log surfacing | Notebook stdout / cell output | Streamed JSONL logs in a UI, plus structured logs on disk |

The remainder of this page expands on the rows that drive the architectural
decision most strongly.

---

## 1. Identity and resource access

This is usually the decisive factor.

ArcGIS Notebook Server runs each notebook inside a container started by the
**Notebook Server site account**. When the notebook touches anything outside
the container — a file share, a SQL Server, an internal HTTPS endpoint —
the identity it presents is either:

- the site service account (typically a single account shared by every
    notebook), or
- a stored credential the analyst pasted into a cell, or
- an ArcGIS Online / Enterprise token (which is only meaningful to other Esri
    services, not to file servers or databases).

In this project the orchestrator runs as a normal Windows process under
**Servy**, which can launch it under **any Windows account you choose**,
including:

- `NT AUTHORITY\NetworkService` for least privilege on a single host.
- A **domain service account** (`DOMAIN\svc-arcpy-orchestration`) that is a
    member of the same security groups your analysts use today.

A domain service account is the practical multiplier. With one account:

- **File-based data** on Windows file shares is reachable over UNC paths
    (`\\server\share\…`) — no container mounts to manage, no SMB credentials
    in code. Permissions on the shares can be granted to the service account
    the same way they would be granted to a person.
- **Database access** can use **Integrated Security** against SQL Server,
    Oracle (via OS Authentication), and PostgreSQL (via SSPI / GSSAPI) —
    connection strings simply read `Trusted_Connection=yes` with no
    passwords stored anywhere. The DBA grants the service account the
    required role and the work is done.
- **Internal HTTPS endpoints** that trust the enterprise root CA work
    out of the box because the Windows certificate store already trusts
    them; no extra CA bundles inside containers.
- **Kerberos constrained delegation** can be configured so the service
    account hops onto another service (e.g. ArcGIS Server, a REST API)
    *as* the originating user. This is essentially impossible to set up
    cleanly across a Docker boundary.

In an audit-heavy environment, "the orchestrator account did it" is also a
much easier story than "the notebook container did it, but actually the
shared site account did it, but actually a cell-level credential did it."

---

## 2. Hardware access

ArcGIS Notebook Server containers are sized by the Notebook Server admin and
**do not have unrestricted access to the host's hardware**:

- CPU and RAM are bound by the container's resource limits. Larger pipelines
    that need 32 GB of RAM or 16 cores have to be re-architected, not just
    re-scheduled.
- **GPU acceleration is not available** in the standard Notebook runtimes.
    Tools like Deep Learning Studio, Detect Objects Using Deep Learning, or
    raster analytics that benefit from CUDA fall back to CPU at best.
- Local SSDs and scratch volumes the host machine has are not exposed.
- Network adapters, including any private/management NICs, are abstracted
    behind container networking.

When the orchestrator runs as a plain process inside ArcGIS Pro's Python
environment:

- It uses **all** the CPU cores and **all** the RAM the host has.
- It has direct access to **the GPU**, which is significant for raster and
    deep-learning workflows.
- It can write intermediate datasets to whatever local SSD the host
    exposes — including `D:\temp` style scratch space that is dramatically
    faster than container-mounted volumes.
- It honours the host's normal Windows networking, including QoS and
    routing.

Put another way: the orchestrator gets the **same** hardware envelope an
analyst gets when they open ArcGIS Pro on that machine and click *Run*.

---

## 3. Software parity with the desktop

Most ArcPy code is written and debugged inside ArcGIS Pro by an analyst.
The Notebook Server runtime is *similar* to Pro's Python environment but is
not identical:

- It is a separate Docker image with its own update cadence.
- It is a curated subset — some toolboxes (e.g. parts of Production
    Mapping, Aviation, Defense, third-party extensions) are not present.
- Custom conda packages have to be baked into a custom runtime image and
    re-baked on every Notebook Server upgrade.
- Geoprocessing tools that depend on local desktop interactions (such as
    those that surface a license check-out dialog) behave differently or not
    at all.

Running on the Pro environment removes the parity question entirely:
whatever the analyst can run interactively from Pro on this machine, the
service can run on a schedule. Package additions are an
`environment.yml` edit and a re-create — not a Docker image rebuild and a
Notebook Server redeployment.

---

## 4. Code organization and review

Notebooks are good for narrative analysis and presentation; they are
**poor production artifacts**:

- `.ipynb` files are JSON. They diff badly, merge worse, and routinely
    accumulate execution-count and cell-output noise that pollute Git
    history.
- Cells encourage out-of-order state and "works on my machine" failures —
    the failure mode where a notebook only runs cleanly because some
    earlier cell was executed twice with different inputs.
- Cross-cutting concerns (logging, config, error handling) are duplicated
    cell-by-cell rather than imported from a shared module.

This project structures code as a normal Python package
(`src/arcpy_orchestration/`) with module-level loggers, a typed config
loader, and reusable functions. Notebooks remain available under
`notebooks/` for exploratory work, but the **scheduled** workflow lives in
plain `.py` modules. The result is:

- Clean Git diffs and reviewable pull requests.
- Real unit tests under `testing/` running on real Python modules.
- IDE support (jump-to-definition, refactoring, type checking) that
    notebook environments do not provide.
- One canonical implementation of cross-cutting concerns rather than N
    copies.

---

## 5. Operations, monitoring, and lifecycle

The orchestration layer in this project (Plombery *or* Dagster, plus Servy
and IIS) is purpose-built for the "scheduled background work" problem.
The project ships first-class support for two interchangeable web
orchestrators so teams can pick whichever fits their operational maturity:

- **[Plombery](plombery_setup_instructions.md)** — single-process FastAPI
    app exposing a per-pipeline page, a *Run now* button, parameterised
    manual runs, schedule editing, and per-run logs streamed live over
    WebSockets. Failures are highlighted; logs are persisted as JSONL on
    disk for downstream ingestion. Minimal moving parts and a fast path
    to a working UI — the right starting point for most teams.
- **[Dagster](dagster_setup_instructions.md)** — webserver + daemon split
    with a richer model of jobs, ops, schedules, sensors, partitions, and
    run observability. Heavier to deploy (two long-running processes
    instead of one) but the better fit for teams that want first-class
    data-orchestration tooling, lineage, and a path to scaling beyond a
    single host.
- **Servy** keeps whichever orchestrator process(es) you choose alive
    across reboots and crashes, captures `stdout` / `stderr` with
    rotation, and lets you change the service account, recovery actions,
    and environment variables through a UI — without writing a Windows
    service in C# or relying on Task Scheduler quirks.
- **IIS** provides standard, audited HTTPS termination using the
    enterprise certificate store and the same authentication primitives
    every other internal web application uses.

The rest of this page's arguments — identity, hardware, software parity,
code organization, licensing — apply identically to either choice.

ArcGIS Notebook Server *does* offer a scheduler, but it is intentionally
simple: one schedule per notebook, no notion of per-task fan-out, no
dependency-aware retries, and no live log stream outside the notebook UI
itself. Comparable functionality on the Notebook Server side typically
means layering an external orchestrator on top anyway.

---

## 6. Licensing

The host machine needs **one ArcGIS Pro Single Use license** assigned to the
service account (or otherwise authorized on the machine). That single license
covers every pipeline the orchestrator runs, regardless of how many analysts
trigger them through the web UI. Plombery, Servy, and IIS impose no
additional licensing.

---

## When ArcGIS Notebooks is still the right answer

To be balanced — this paradigm is the wrong choice when:

- The audience is **analysts authoring shareable narratives**, not
    operations engineers running scheduled jobs.
- The workload **must run inside ArcGIS Enterprise's identity model**
    (e.g. it acts on behalf of a named user and respects portal sharing
    rules from inside Esri-managed code).
- You need **multi-tenant isolation** between many users running ad-hoc
    work on the same machine — containers give you that for free,
    whereas a single Pro environment does not.
- You **do not have a Windows host** to run ArcGIS Pro on, and your
    Esri footprint is Notebook Server in a Linux/Kubernetes
    environment.

In those scenarios, keep using Notebooks. Where the requirement is
"run an ArcPy pipeline on a schedule, on real hardware, against
real file shares and databases, under a real account" — this project's
paradigm is the simpler answer.
