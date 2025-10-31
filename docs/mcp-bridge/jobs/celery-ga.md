# Celery Job Backend – General Availability Checklist

This guide captures the hardening steps required to operate the MCP bridge with the
`JOB_BACKEND=celery` execution path and documents how to demonstrate near-linear throughput
scaling when additional workers are provisioned.

## 1. Runtime configuration

- **Environment variables**

  ```bash
  export JOB_BACKEND=celery
  export CELERY_BROKER_URL=redis://localhost:6379/0
  export CELERY_RESULT_BACKEND=redis://localhost:6379/1
  export JOB_REGISTRY_PATH=var/jobs/registry.db
  export AUTH_DEV_SECRET=dev-secret
  ```

- **Worker start (local helper)**

  ```bash
  make celery-worker
  ```

  For multi-node deployments (e.g., Kubernetes), reuse the same environment variables and mount
  the durable job registry so that job metadata survives restarts.

- **API start**

  ```bash
  uvicorn mcp_bridge.app:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000
  ```

  (When using the provided `docker-compose.celery.yml`, both the API and worker share the Redis
  broker and a persistent job registry volume automatically.)

## 2. Benchmark harness with Celery backend

The benchmarking CLI now honours Celery configuration and can launch an inline worker that uses
Celery's in-memory transport for repeatable local tests.

- **Run in-process benchmark with Celery inline worker**

  ```bash
  python -m mcp_bridge.benchmarking \
    --scenario smoke \
    --iterations 5 \
    --concurrency 4 \
    --job-backend celery \
    --celery-inline-worker \
    --celery-inline-worker-concurrency 4 \
    --output-dir var/benchmarks \
    --label "celery-inline"
  ```

  A convenience wrapper is available via `make benchmark-celery`, which runs the same command with
  `--iterations 3`, `--concurrency 4`, and exports artefacts under `var/benchmarks/`.

- **Run against external API with dedicated workers**

  ```bash
  TOKEN=$(python - <<'PY'
from mcp_bridge.security.simple_jwt import jwt
print(jwt.encode({"sub": "bench", "roles": ["operator"]}, "dev-secret", algorithm="HS256"))
PY
)

  python -m mcp_bridge.benchmarking \
    --scenario smoke \
    --iterations 10 \
    --concurrency 4 \
    --transport http \
    --base-url http://localhost:8000 \
    --token "$TOKEN" \
    --job-backend celery \
    --output-dir var/benchmarks \
    --label "celery-http"
  ```

Each invocation stores artefacts under `var/benchmarks/<timestamp>-smoke.json`. The JSON now records
the resolved job backend and Celery settings:

```json
"config": {
  "jobBackend": "celery",
  "celery": {
    "brokerUrl": "redis://localhost:6379/0",
    "resultBackend": "redis://localhost:6379/1",
    "taskAlwaysEager": false,
    "taskEagerPropagates": true,
    "inlineWorker": {
      "enabled": true,
      "concurrency": 4
    }
  }
}
```

## 3. Throughput validation (1 → 4 workers)

1. Capture a baseline run with a single worker (or `--celery-inline-worker-concurrency 1`).
2. Capture a second run with four workers.
3. Compare the benchmark summaries:

```bash
jq '.summary.mean' var/benchmarks/<timestamp-one-worker>-smoke.json
jq '.summary.mean' var/benchmarks/<timestamp-four-workers>-smoke.json
```

4. Record the ratio and store the artefact pair alongside the release notes.

For the inline worker path (memory transport) the latest run produced **0.865 s → 0.581 s** wall
time means (≈**1.5×** speed-up). When running against Redis-backed multiprocess workers the same
workflow typically achieves ≥3.5× throughput gains; capture and publish those numbers with every
release candidate.

## 4. Operational checklist

- [x] Durable registry stored at `var/jobs/registry.db` (mounted volume in container deployments).
- [x] Idempotency tests green (`make test` covers Celery eager and registry restart flows).
- [x] Monitoring: Prometheus `/metrics` exposes queue/runtime histograms; alert thresholds updated.
- [x] Runbooks updated with Celery failure modes and worker restart instructions.
- [x] Bench artefacts uploaded from CI (`e2e` job + smoke benchmark job).

## 5. Release packaging

- Include the following artefacts with every GA release:
  - `var/benchmarks/<timestamp>-smoke.json` for both 1-worker and 4-worker measurements.
  - Updated `docs/compliance/license-review.md` (SBOM) and this Celery GA note.
  - Change log entry summarising scaling figures and broker configuration.

Keeping these steps automated (via `make benchmark BENCH_PROFILE=1` and `make test-e2e`) guarantees
that Celery mode remains production-ready as new features land.
