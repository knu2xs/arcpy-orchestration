# Plombery Logging Integration

How `arcpy_orchestration` log output is forwarded into the
[Plombery](https://lucafaggianelli.com/plombery/) web UI without changing any
module-level logging code.

---

## Quick Use

There is **nothing to configure**. Just import `arcpy_orchestration` somewhere in your
Plombery orchestrator script (directly or transitively) and any log records its modules
emit will appear in the Plombery web UI for the active run:

```python
from plombery import task, Trigger, register_pipeline

import arcpy_orchestration  # noqa: F401 — wires logs into the Plombery UI


@task
async def my_task():
    from arcpy_orchestration.some_module import do_work
    return do_work()
```

Inside `arcpy_orchestration` modules, keep using the standard project logger pattern —
no changes required:

```python
from arcpy_orchestration.utils import get_logger

logger = get_logger(__name__, level="DEBUG", add_stream_handler=False)
```

!!! note
    The Plombery handler is installed on the package logger by
    `arcpy_orchestration/__init__.py` at import time. It is safe to install
    unconditionally — records are silently discarded when Plombery is not installed
    or when no pipeline is currently running, so the same package works unchanged in
    notebooks, ArcGIS Pro toolboxes, and standalone scripts.

!!! tip
    Records emitted before a Plombery task starts (for example, during module import)
    are dropped because there is no run to attach them to. If you also want to capture
    startup-time messages, configure a stream handler or logfile handler at the script
    entry point.

---

## How It Works

### The problem

Plombery's `get_logger()` (called from inside a task) returns a
`logging.LoggerAdapter` wrapping a logger named
`plombery.{run_id}` or `plombery.{run_id}-{task_id}`. That logger has two handlers
attached:

- A `FileHandler` writing JSONL to disk (consumed by the runs API).
- A `WebSocketHandler` streaming records over Socket.IO to the web UI.

Crucially, **these handlers are attached to a Plombery-specific named logger, not the
root logger**. The standard Python logging propagation chain for an
`arcpy_orchestration` module logger looks like this:

```
arcpy_orchestration.some_module  →  arcpy_orchestration  →  root
```

It never touches `plombery.{run_id}`. So a function in `arcpy_orchestration` that calls
`logger.info(...)` produces no output in the Plombery UI by default — the two logger
hierarchies are completely disjoint.

### The solution: `PlomberyHandler`

A new `logging.Handler` subclass, [`PlomberyHandler`](api.md), installed on the
`arcpy_orchestration` package logger:

```python
class PlomberyHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            from plombery.pipeline.context import (
                pipeline_context, task_context, run_context,
            )

            task = task_context.get(None)
            pipeline_run = run_context.get()

            logger_name = f"plombery.{pipeline_run.id}"
            if task:
                logger_name += f"-{task.id}"

            plombery_logger = logging.getLogger(logger_name)
            if plombery_logger.handlers:
                plombery_logger.handle(record)
        except LookupError:
            # No active Plombery pipeline context; discard silently.
            pass
```

The key design choices:

1. **Resolve the run logger at `emit()` time.** Plombery's pipeline, task, and run are
    exposed as
    [`contextvars.ContextVar`](https://docs.python.org/3/library/contextvars.html)
    instances and are only set while a task is executing. Reading them inside `emit()`
    means each record is routed to the correct run logger, even when many runs share
    the same process.

2. **Forward via `Logger.handle(record)`, not by re-attaching handlers.** Calling
    `handle()` on the existing `plombery.{run_id}` logger lets Plombery's own
    `JsonFormatter`, `FileHandler`, and `WebSocketHandler` do their job unchanged.
    No formatter is set on `PlomberyHandler` itself — that would only get in the way.

3. **Catch `LookupError` and `ImportError` to handle "no active pipeline" and
    "Plombery not installed".** Reading an unset
    `ContextVar` (with no default) raises `LookupError`; importing
    `plombery.pipeline.context` in an environment without Plombery raises
    `ImportError`. Catching both makes it safe to install `PlomberyHandler`
    unconditionally from the package's `__init__.py`, so the same package works in
    Plombery, ArcGIS Pro toolboxes, notebooks, and standalone scripts without
    branching on the runtime environment.

4. **No persistent state.** The handler holds no file descriptors, sockets, or
    references to Plombery objects. It cannot leak resources across runs (which was the
    failure mode of [Plombery issue #491](https://github.com/lucafaggianelli/plombery/issues/491)
    when callers added a fresh `FileHandler` per run).

### The `get_logger` integration

`get_logger` already had an unimplemented `add_plombery_handler: bool = False`
parameter. It was wired up alongside the existing `add_arcpy_handler` block:

```python
if add_plombery_handler:
    if not any(isinstance(h, PlomberyHandler) for h in logger.handlers):
        logger.addHandler(PlomberyHandler())
```

The `isinstance` guard makes the call **idempotent** — repeated calls during interactive
development or in pytest sessions will not stack duplicate handlers.

### Why install on the package logger and not module loggers

`PlomberyHandler` is installed once on the `arcpy_orchestration` package logger from
the package's `__init__.py`:

```python
# src/arcpy_orchestration/__init__.py
logger = utils.get_logger(
    "arcpy_orchestration",
    level="DEBUG",
    add_stream_handler=False,
    add_plombery_handler=True,
)
```

Every module logger inside the package
(`arcpy_orchestration.utils`, `arcpy_orchestration.config`, …) is created with
`propagate=True`, so its records walk up the hierarchy:

```
arcpy_orchestration.utils._data  →  arcpy_orchestration.utils
                                  →  arcpy_orchestration   ← PlomberyHandler emits here
                                  →  root
```

This avoids the two main pitfalls of attaching the handler at the module level:

- **No duplicate emissions.** Adding the handler on both a child and an ancestor logger
    would emit each record twice.
- **No need to modify existing modules.** The package-level install picks up every
    current and future module automatically.

### What ends up in the Plombery UI

When a task runs, `arcpy_orchestration` log records flow through the following path:

```
some_module.logger.info("…")
        │  (propagation)
        ▼
arcpy_orchestration logger
        │  (PlomberyHandler.emit reads ContextVars)
        ▼
plombery.{run_id}[-{task_id}] logger
        │
        ├─► FileHandler  →  .data/runs/run_{id}/logs.jsonl
        └─► WebSocketHandler  →  live stream to the web UI
```

The `loggerName` field in the JSONL output reflects Plombery's run-scoped logger name,
and the `pipeline` / `task` fields are stamped by Plombery's `JsonFormatter` —
exactly as if the task had called `plombery.get_logger()` directly.

---

## Caveats and Trade-offs

- **Records before the first task run are dropped.** `PlomberyHandler` has no
    fallback destination by design. If you want startup-time messages preserved, also
    pass `add_stream_handler=True` and/or a `logfile_path` to the same `get_logger`
    call.
- **The handler imports `plombery.pipeline.context` lazily.** This keeps
    `arcpy_orchestration` usable in environments where Plombery is not installed.
    The import only happens on the first log record after a task starts.
- **`PlomberyHandler` does not honour Plombery's log-level filters in the UI.** All
    records the package logger accepts will reach the run logger. Filter at the
    `arcpy_orchestration` logger level (the `level=` argument) if you need to suppress
    noisy modules.
