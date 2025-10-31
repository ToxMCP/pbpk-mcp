# Distributed Job Execution Architecture

## Overview

The MCP bridge now supports two job execution backends:

| Backend | Description | When to use |
|---------|-------------|-------------|
| `thread` (default) | In-process `ThreadPoolExecutor` that executes jobs inside the API process.  Simple, zero external dependencies. | Local development, unit tests, single-instance deployments. |
| `celery` | Celery task queue driving dedicated worker processes.  Uses the same tool payloads but enables horizontal scaling and persistence (when broker/result backends support it). | Production deployments requiring long-running jobs, retries, or worker isolation. |

The job backend is selected via `JOB_BACKEND` in configuration (`thread` or `celery`).  Celery-specific settings (broker URL, result backend, eager mode) are exposed as `CELERY_*` environment variables.

## Component Diagram

```
┌────────────┐    submit_job     ┌───────────┐      enqueue       ┌──────────────┐
│ MCP API    │ ───────────────▶ │ JobService│ ─────────────────▶ │ Celery Broker│
│ (FastAPI)  │                  │ (celery)  │                    │ (e.g. Redis) │
└────────────┘                  └─────┬─────┘                    └───────┬──────┘
       ▲                             │                                   │
       │  poll /events               │ result + status                   │ deliver
       │                             ▼                                   ▼
  ┌────────────┐        ┌─────────────────────┐           ┌────────────────────┐
  │ SSE Client │ ◀──────│ AsyncResult monitor │ ◀──────── │ Celery Workers      │
  └────────────┘        └─────────────────────┘           │ (Run simulation)   │
                                                          └────────────────────┘
```

* **API layer** creates the job record and enqueues the task.  Job state snapshots are exposed via `/get_job_status` and streamed through `/jobs/{job_id}/events`.
* **JobService** encapsulates backend-specific orchestration.  For Celery, it:
  * Configures the Celery app (broker/result backend, eager mode).
  * Enqueues tasks with deterministic task IDs (`job_id`).
  * Synchronises job status by querying the Celery result backend (`AsyncResult`).
* **Celery workers** bootstrap an adapter instance per task, execute the simulation, and return the result handle.
* **Clients** poll or stream SSE to react to state transitions (queued → running → succeeded/failed/cancelled).

## State Lifecycle

1. **Submitted** – record stored in-memory and persisted to the durable registry (SQLite-backed `JOB_REGISTRY_PATH`). SSE emits `queued` event.
2. **Running** – worker pulls task, job service marks `running`. SSE emits `running` event.
3. **Terminal** – `succeeded`, `failed`, `timeout`, or `cancelled`.
   * Celery workers return result ID; job service stores it for `/get_simulation_results`.
   * Failures include structured `error` payloads (propagated to clients).

### Retention & Cleanup

- Completed job metadata is retained for `JOB_RETENTION_SECONDS` (default 7 days). On startup and after every terminal transition the registry purges expired rows and associated result payloads.
- The population claim-check store applies the same retention window (configurable via `POPULATION_RETENTION_SECONDS`) and deletes stale result directories as part of the purge cycle.
- Set either value to `0` to disable automatic cleanup—useful for local debugging when you want to inspect the raw artefacts.
- Purge activity is logged at `DEBUG` level (`job_registry.purged`, `population_results.purged`) so long-running deployments can monitor cleanup cadence.

Retries are tracked per job; Celery `RETRY` states map back to `running` while incrementing the attempt counter.

## Configuration

```env
# Job backend selection
JOB_BACKEND=thread              # or celery

# Celery-specific settings
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_ALWAYS_EAGER=false
CELERY_TASK_EAGER_PROPAGATES=true
# Persist job metadata locally for API restarts (override to point at a durable volume)
JOB_REGISTRY_PATH=var/jobs/registry.db
```

See `docs/mcp-bridge/operations/celery-runbook.md` for a full deployment and incident response guide.

### Running Workers

```bash
# Start the API (thread or celery backend depending on configuration)
uvicorn mcp_bridge.app:create_app --factory

# In another terminal, start a Celery worker when JOB_BACKEND=celery
make celery-worker
```

Eager mode (`CELERY_TASK_ALWAYS_EAGER=true`) is useful for local tests and the compliance harness because tasks execute inline without a dedicated worker.

## Future Work

* **Durable job registry backend** – ✅ implemented via SQLite persistence (API restarts recover queued/running jobs and mark unfinished ones as failed).
* **Progress reporting** – stream intermediate adapter logs or percentage updates back to Celery result backend.
* **Observability** – integrate Celery events into existing audit trail, exposing metrics (queue depth, latency) to the monitoring stack.

This document fulfils Task 23 ▸ subtask 1 (“Design distributed job architecture”).
