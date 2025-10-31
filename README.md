# MCP Bridge Server

Bridge service exposing Open Systems Pharmacology Suite capabilities via the Model Context Protocol.

## Getting Started

```bash
make install
make lint
make test
# Provision reference parity data and run the deterministic parity suite
make fetch-bench-data
make parity
# Enforce literature extraction accuracy thresholds against the gold set
make goldset-eval
```

### Benchmarking

- `make benchmark` runs the smoke scenario locally (in-process ASGI transport) and stores JSON artefacts under `var/benchmarks/`.
- Append `BENCH_PROFILE=1` to capture a cProfile trace alongside the JSON (e.g. `make benchmark BENCH_PROFILE=1`).
- Compare a result against the repository baseline with `python scripts/check_benchmark_regression.py --benchmark var/benchmarks/<file>.json --baseline benchmarks/thresholds/smoke.json`.

### Idempotent tool calls

- Provide an `idempotencyKey` field when calling `/mcp/call_tool` (or the `Idempotency-Key` header once exposed on REST endpoints) to deduplicate repeated submissions.
- Duplicate payloads with the same key return the original job metadata; mismatched payloads respond with HTTP `409` so clients can remediate.

Detailed walkthroughs for REST and agent flows live under
`docs/mcp-bridge/getting-started/quickstart-cli.md` and
`docs/mcp-bridge/getting-started/quickstart-agent.md`.

### Agent Workflows

- `run_agent.py demo` executes the end-to-end confirm-before-execute pipeline using the in-memory adapter.
- `run_agent.py` (interactive mode) exercises the LangGraph agent loop and prompts for confirmation before
  mutating or running simulations.
- Follow the Quickstart guides in `docs/mcp-bridge/getting-started/` for step-by-step tutorials.
- REST surface area and configuration variables are documented in `docs/mcp-bridge/reference/api.md`
  and `docs/mcp-bridge/reference/configuration.md`.
- Documentation for prompt policies and tooling lives in `docs/mcp-bridge/agent-prompts.md`.
- Authentication/authorization behaviour and configuration is documented in `docs/mcp-bridge/authentication.md`.
- Immutable audit trail design and verification plan is in `docs/mcp-bridge/audit-trail.md`.
- Value-oriented scenarios live in the [use-case packs](use-cases/README.md) (notebooks covering sensitivity, population scale, and literature-assisted calibration).

### Sensitivity Analysis

- The reusable sensitivity utilities live in `src/mcp_bridge/agent/sensitivity.py`.
- Refer to `docs/mcp-bridge/sensitivity-analysis.md` for configuration and workflow details.
- Unit coverage is provided via `tests/unit/test_sensitivity_analysis.py`.

## Project Layout

- `src/` – package source code.
- `tests/` – unit and integration tests.
- `docs/` – architecture, contracts, and threat model reference material.
- `docs/tools/` – per-tool documentation for the MCP surface.

## Configuration

Settings are supplied through environment variables (a `.env` file is supported):

- `HOST` – interface the HTTP server binds to (default `0.0.0.0`).
- `PORT` – TCP port for the HTTP server (default `8000`).
- `LOG_LEVEL` – log level for structlog output (default `INFO`).
- `SERVICE_NAME` – emitted service identifier (default `mcp-bridge`).
- `SERVICE_VERSION` – override for the version reported in `/health` (defaults to package version).
- `ENVIRONMENT` – environment tag (default `development`).
- `MCP_MODEL_SEARCH_PATHS` – optional colon-separated list of directories that contain PBPK
  `.pkml` files. If unset, the server allows paths under `tests/fixtures` for local testing.
- `ADAPTER_BACKEND` – `inmemory` (default) or `subprocess`. The latter shells out to an R/ospsuite bridge.
- `ADAPTER_REQUIRE_R_ENV` – set to `true` to fail startup if R/ospsuite cannot be detected (default `false`).
- `ADAPTER_TIMEOUT_MS` – default timeout (in milliseconds) for adapter operations (default `30000`).
- `ADAPTER_R_PATH` / `ADAPTER_R_HOME` / `ADAPTER_R_LIBS` – explicit R binary, home, and library locations.
- `OSPSUITE_LIBS` – absolute path to ospsuite R libraries when using the subprocess backend.
- `ADAPTER_MODEL_PATHS` – colon-separated allow list of `.pkml` directories when using the subprocess backend.
- `ADAPTER_TO_THREAD` – when `true` (default) FastAPI routes run blocking adapter calls in background threads to protect the event loop.
- `JOB_WORKER_THREADS` – size of the in-process job worker pool (default `2`).
- `JOB_BACKEND` – select `thread` (default) or `celery` to offload work to distributed workers.
- `JOB_TIMEOUT_SECONDS` – execution timeout for queued simulation jobs (default `300`).
- `JOB_MAX_RETRIES` – automatic retry attempts for failed jobs (default `0`).
- `JOB_REGISTRY_PATH` – SQLite database used to persist job metadata across API restarts (default `var/jobs/registry.db`; `.json` paths are automatically converted).
- `SESSION_BACKEND` – `memory` (default) or `redis` for the simulation session registry.
- `SESSION_REDIS_URL` – connection string used when `SESSION_BACKEND=redis`.
- `SESSION_REDIS_PREFIX` – Redis key prefix for session entries (default `mcp:sessions`).
- `SESSION_TTL_SECONDS` – optional TTL applied to Redis session records; leave unset to disable expiry.
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` – Celery connection URIs when `JOB_BACKEND=celery`.
- `CELERY_TASK_ALWAYS_EAGER` / `CELERY_TASK_EAGER_PROPAGATES` – toggle inline execution for tests and whether exceptions propagate.
- `AUDIT_ENABLED` – toggles immutable audit logging (default `true`).
- `AUDIT_STORAGE_PATH` – filesystem path used for audit JSONL logs (default `var/audit`).
- `AUDIT_STORAGE_BACKEND` – `local` (default) or `s3` to enable Object Lock uploads.
- `AUDIT_S3_BUCKET` / `AUDIT_S3_PREFIX` / `AUDIT_S3_REGION` – S3 settings for audit storage when backend is `s3`.
- `AUDIT_S3_OBJECT_LOCK_MODE` / `AUDIT_S3_OBJECT_LOCK_DAYS` – configure S3 Object Lock governance/compliance retention.
- `AUDIT_S3_KMS_KEY_ID` – optional KMS key for encrypting audit events at rest in S3.
- `AUDIT_VERIFY_LOOKBACK_DAYS` – window (days) verified by the scheduled audit integrity job (default `1`).
- `MCP_RUN_R_TESTS` – opt-in flag for R-dependent integration tests (`1` runs them, default `0` skips).
- `AUTH_ISSUER_URL` / `AUTH_AUDIENCE` / `AUTH_JWKS_URL` / `AUTH_JWKS_CACHE_SECONDS` – configure JWT validation against your IdP.
- `AUTH_DEV_SECRET` – optional HS256 secret for local development/testing tokens.

Refer to `docs/mcp-bridge/reference/configuration.md` for an exhaustive table of supported variables.

### R / ospsuite Integration

By default the application uses the in-memory adapter suitable for local development and CI without
an R toolchain. To exercise the subprocess-backed adapter, set:

```bash
export ADAPTER_BACKEND=subprocess
export MCP_MODEL_SEARCH_PATHS=/path/to/models
export MCP_RUN_R_TESTS=1
```

You can then run the full test suite (including R-dependent integrations) with:

```bash
make test
```

If the R environment is optional, leave `ADAPTER_REQUIRE_R_ENV` unset so the service continues to
start even when ospsuite is unavailable. Setting `ADAPTER_REQUIRE_R_ENV=true` enforces a hard failure.

Supported OSPSuite releases and tested environments are tracked in
`docs/mcp-bridge/reference/compatibility.md`; review it when upgrading
automation binaries or base images.

### Durable Session Registry (Redis)

Set the session registry backend to Redis to survive API restarts and support multi-instance
deployments:

```bash
export SESSION_BACKEND=redis
export SESSION_REDIS_URL=redis://localhost:6379/2
export SESSION_REDIS_PREFIX=mcp:sessions
# Optional – expire sessions after 24 hours
export SESSION_TTL_SECONDS=86400
```

Ensure the Redis instance is reachable from both the API and Celery workers (if enabled). The
registry stores the JSON representation of `SimulationHandle` objects and metadata under the
configured prefix. Use `python -m mcp_bridge.runtime.session_cli dump --pretty` (see docs) to
inspect active sessions.

### Immutable Audit Trail in S3

Production deployments can ship audit events directly to an S3 bucket configured with Object Lock:

```bash
export AUDIT_STORAGE_BACKEND=s3
export AUDIT_S3_BUCKET=my-audit-bucket
export AUDIT_S3_PREFIX=bridge/audit
export AUDIT_S3_REGION=us-east-1
export AUDIT_S3_OBJECT_LOCK_MODE=governance
export AUDIT_S3_OBJECT_LOCK_DAYS=90
```

Each event is stored as an immutable object (`prefix/YYYY/MM/DD/<timestamp>-<eventId>.jsonl`) with
hash chaining preserved across restarts. Ensure the target bucket has Object Lock enabled in the
same mode you configure. Optional `AUDIT_S3_KMS_KEY_ID` allows encrypting objects with a customer
managed KMS key.

To periodically verify the chain and retention policy, run:

```bash
python -m mcp_bridge.audit.verify s3://$AUDIT_S3_BUCKET/$AUDIT_S3_PREFIX \
  --object-lock-mode $AUDIT_S3_OBJECT_LOCK_MODE \
  --object-lock-days $AUDIT_S3_OBJECT_LOCK_DAYS
```

To run the scheduled verification logic that respects `AUDIT_VERIFY_LOOKBACK_DAYS`, execute:

```bash
python -m mcp_bridge.audit.jobs
```

### Non-blocking Adapter Calls

Set `ADAPTER_TO_THREAD=true` (default) to offload adapter-bound work—such as `load_simulation` and
parameter access—to background threads. This keeps the FastAPI event loop responsive under load
while maintaining structured logging and correlation IDs. Disable the flag if you embed the server
in an environment that manages dispatching differently.

### Distributed Job Backend (Celery)

Long-running simulation jobs can execute via Celery workers instead of the in-process thread pool.
Switching is configuration-only:

```bash
export JOB_BACKEND=celery
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
export CELERY_TASK_ALWAYS_EAGER=false
```

Run the API as usual (for example with `uvicorn mcp_bridge.app:create_app --factory`) and start a
worker in a separate shell:

```bash
make celery-worker
```

For quick smoke testing without a dedicated worker you can enable eager mode:

```bash
export JOB_BACKEND=celery
export CELERY_BROKER_URL=memory://
export CELERY_RESULT_BACKEND=cache+memory://
export CELERY_TASK_ALWAYS_EAGER=true  # tasks execute inline, no worker required
```

Celery job submissions are persisted to `JOB_REGISTRY_PATH` (default `var/jobs/registry.json`) so
`/get_job_status` continues to work after API restarts. Clean up the file when resetting local state.

For a turnkey local stack (API + worker + Redis) use:

```bash
docker compose -f docker-compose.celery.yml up --build
```

The compose file mounts `./var` so audit logs and the job registry survive container restarts.
Detailed operational guidance lives in `docs/mcp-bridge/operations/celery-runbook.md`.

See `docs/mcp-bridge/distributed-job-architecture.md` for a deeper dive into the queue topology,
state transitions, and production considerations.

### HPC Submission Stub (Slurm)

The job service now ships with a mocked Slurm scheduler that exercises external job identifiers and
queue delays without needing access to an HPC cluster:

```bash
export JOB_BACKEND=hpc
export HPC_STUB_QUEUE_DELAY_SECONDS=0.1  # optional delay before dispatch
uvicorn mcp_bridge.app:create_app --factory
```

Job status responses will include an `externalJobId` and the audit trail records
`job.<type>.hpc_submitted` / `job.<type>.hpc_dispatched` events. A dedicated regression keeps the
stub green:

```bash
make test-hpc
```

Design details and operational guidance live in `docs/operations/hpc.md`.

### Operations Runbook

Day-to-day procedures—startup, health checks, incident drills, and rollback—are
documented in `docs/operations/runbook.md`. Review it before on-call rotations
and update the drill log after mitigation exercises.

For release governance, follow the [change management checklist](docs/mcp-bridge/operations/change-management.md)
and ensure every PR includes smoke benchmark and alert verification evidence.

## Container Workflow

```bash
make build-image          # Build the runtime image
make run-image            # Run locally (binds :8000)
curl http://localhost:8000/health
```

The image runs as a non-root user and includes an embedded health check that polls `/health` every 30 seconds.
