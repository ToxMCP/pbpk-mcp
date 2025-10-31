# Performance & Scalability Plan (Draft)

## 1. Goals and Success Criteria

- Establish baseline latency and throughput targets for high-impact MCP tools.
- Define how we will measure performance across synchronous and asynchronous workflows.
- Provide an initial view of instrumentation and reporting needed to track regressions.

## 2. Benchmarking Scope

We will cover the full lifecycle of a PBPK simulation session:

1. Loading simulations (`load_simulation`).
2. Parameter inspection and mutation (`get_parameter_value`, `set_parameter_value`).
3. Single-run simulations (`run_simulation`).
4. Long-running population workloads (`run_population_simulation`, `get_population_results`).
5. Job orchestration surfaces (`get_job_status`) to validate queue latency and completion metadata.

Ancillary endpoints (health, auth, metadata) are out of scope unless profiling exposes them as bottlenecks.

## 3. Benchmarking Methodology Overview

### 3.1 Harness Strategy
- Python CLI that exercises MCP tools directly through the HTTP API and via the local `mcp` client to capture both transport layers.
- Supports warm-up iterations, configurable concurrency, and fixed random seeds for repeatability.
- Emits structured JSON summaries per run for CI regression tracking.

### 3.2 Measurement Phases
- **Cold start:** first request after process boot to quantify adapter initialisation cost.
- **Steady state:** repeated invocations with warmed caches (simulation handles, parameter caches).
- **Stress:** concurrency sweeps (1, 4, 8 workers) to uncover thread pool saturation or R bridge contention.

### 3.3 Instrumentation
- Built-in timing via `time.perf_counter()`.
- Optional OS-level sampling using `py-spy` or `perf` for hotspots (triggered in profiling runs).
- Prometheus-style metrics hook (re-using FastAPI instrumentation once enabled) to export latency histograms.

## 4. Performance Targets (Initial Draft)

| Scenario | Metric | Target | Notes |
| --- | --- | --- | --- |
| `load_simulation` (5–10 MB `.pkml`) | P95 latency | ≤ 2.5 s | Measured post cold-start; assumes local SSD. |
| Parameter read (`get_parameter_value`) | P95 latency | ≤ 150 ms | Cached responses should stay near 50 ms. |
| Parameter write (`set_parameter_value`) | P95 latency | ≤ 200 ms | Includes adapter round-trip and audit logging. |
| `run_simulation` job submission | Queue wait | ≤ 1 s | Time from POST to job marked RUNNING in registry. |
| `run_simulation` execution | Completion time (baseline model) | ≤ 30 s | Uses demo model with deterministic inputs. |
| `run_population_simulation` (1k subjects × 10 replicates) | Completion time | ≤ 12 min | Executed on 8 vCPU / 32 GB RAM baseline. |
| `get_population_results` chunk retrieval | Throughput | ≥ 50 MB/s | Streaming from local filesystem-backed store. |

## 5. Dataset and Workload Selection

| Tier | Purpose | Dataset / Configuration | Notes |
| --- | --- | --- | --- |
| Smoke | Validate harness & regressions in CI | `tests/fixtures/demo.pkml` (single subject) | Replicate current unit-test fixture; completes in < 5 s. |
| Baseline | Track realistic single-subject behaviour | `var/models/standard/<model>.pkml` (10–25 MB) | Pull from OSP public PBPK library (e.g., Midazolam adult model). Stored under Git LFS or fetched via Make target. |
| Stress | Exercise population workloads | Population configuration committed under `var/workloads/population_1k.json` | Defines 1000 subjects × 10 replicates with deterministic seeds for reproducibility. |
| Extreme | Capacity testing (optional, manual) | External HPC dataset (10k+ subjects) staged outside repo | Run on demand during release readiness; document results in `reports/perf/`. |

Action items:
- **DONE** – `make fetch-bench-data` now provisions reference parity models under `var/models/standard` and validates expected metrics in `reference/parity/expected_metrics.json`.
- **DONE** – CI workflow executes `make benchmark BENCH_PROFILE=1`, uploads the JSON + profile artefacts, and gates PRs via `scripts/check_benchmark_regression.py` using ±10% p95 tolerance.
- Document expected storage footprint (≤ 1 GB) in `README.md` once assets are wired in.
- Maintain profiling notes and hotspots in `docs/mcp-bridge/performance-profiling.md`.

## 6. Metrics Collection and Reporting

- Every harness execution writes `var/benchmarks/<timestamp>.json` containing:
  - Scenario metadata (tool, dataset, concurrency, run configuration hash).
  - Latency distribution (min, p50, p90, p95, max).
  - CPU utilisation (avg/max) and memory high-water mark derived from `psutil`.
  - Adapter-specific timings (queue wait, execution time, result serialisation) when available.
- CI smoke jobs archive the JSON and surface key values via GitHub Actions summary.
- Local runs can be plotted with a companion `make benchmark-report` target that renders Markdown charts via `matplotlib` and saves to `reports/perf/latest.md`.
- For asynchronous workloads, JobService emits audit events already; extend analysis script to compute queue wait vs execution deltas from those logs.

### 6.1 CI Gate

- Set `MCP_BENCHMARK_RESULT=<path-to-json>` (and optionally `MCP_BENCHMARK_BASELINE=<baseline.json>`)
  before invoking the test suite. `pytest tests/perf/test_benchmark_thresholds.py` calls
  `scripts/check_benchmark_regression.py` and fails the build if thresholds are exceeded.
- Typical pipeline order:
  1. `make benchmark` (produces `var/benchmarks/<timestamp>.json`).
  2. Export `MCP_BENCHMARK_RESULT` pointing at that artefact.
  3. Run `pytest` (the perf test skips automatically when the variable is absent for local dev).

## 7. Acceptance Gates and Regression Policy

- A change fails CI if any tracked metric regresses by more than 10% over the Baseline tier targets or exceeds absolute limits in Section 4.
- Stress tier runs weekly; if completion time exceeds `≤ 12 min` by >10%, task owner opens a follow-up issue with profiling artifacts.
- Cold-start `load_simulation` must stay below 5 s even on constrained developer laptops (4 vCPU / 16 GB RAM); warn (but do not block) if it rises above 3.5 s.
- Throughput targets for `get_population_results` assume local filesystem; when object storage is enabled, update thresholds but retain ≥ 30 MB/s minimum.
- Any manual Extreme tier assessment must end with a short summary committed under `reports/perf/` describing scaling recommendations and environment details.

## 8. Adapter Optimization Outcomes (2025-10-25)

### 8.1 Smoke Scenario Benchmarks

| Run ID | Adapter mode | Iterations | P95 wall (ms) | Δ vs 2025-10-16 | Source |
| --- | --- | --- | --- | --- | --- |
| 20251016T170255Z-smoke | Subprocess (cold start) | 1 | 33.258 | Baseline | `var/benchmarks/20251016T170255Z-smoke.json` |
| 20251025T004749Z-smoke | Subprocess (first warm call) | 1 | 20.006 | −40% | `var/benchmarks/20251025T004749Z-smoke.json` |
| 20251025T004927Z-smoke | Subprocess (warm pool, steady) | 5 | 18.674 | −44% | `var/benchmarks/20251025T004927Z-smoke.json` |
| 20251025T155755Z-smoke | In-memory + adapter offload | 5 | 20.675 | −38% | `var/benchmarks/20251025T155755Z-smoke.json` |

Key deltas:

- `run_simulation` P95 dropped from 16.819 ms to 3.126 ms (−81%) once the warm process pool stayed primed; see `var/benchmarks/20251016T170255Z-smoke.json` and `var/benchmarks/20251025T004927Z-smoke.json`.
- `load_simulation` remains the dominant contributor at ~6–8 ms; additional I/O batching is the next candidate should cold-start latency regress.
- `asyncio.to_thread` offloading keeps FastAPI request latency similar to the warm-pool run while protecting the event loop (see `ADAPTER_TO_THREAD` in README).
- Process metrics confirm CPU utilisation stayed <8% across runs, so the current improvements stem from removing subprocess start overhead rather than additional compute.

Reproduce the steady-state benchmark locally:

```bash
PYTHONPATH=src python -m mcp_bridge.benchmarking \
  --scenario smoke \
  --iterations 5 \
  --transport asgi \
  --simulation-file tests/fixtures/demo.pkml \
  --label subprocess-baseline
```

The command writes JSON artefacts under `var/benchmarks/` (and reuses the configured adapter backend from your environment).

### 8.2 Warm Subprocess Pool Rollout & Adapter Offloading

- The Subprocess adapter now keeps worker processes alive between tool invocations; no additional configuration is required beyond `ADAPTER_BACKEND=subprocess`.
- Pre-warm environments by running a single smoke iteration during deployment health checks (`make benchmark`), ensuring the pool is hydrated before exposing traffic.
- Monitor `var/benchmarks/*-smoke.json` size and the audit trail (`var/audit/`) to confirm the warm pool restarts when R workers exit unexpectedly.
- `ADAPTER_TO_THREAD=true` offloads blocking adapter work. Confirm the flag remains enabled in production to preserve event loop responsiveness; disable only if embedding in an external worker model.

### 8.3 rpy2 Adapter Spike (Go/No-Go Snapshot)

- Prototype validated that ospsuite libraries can be imported via `rpy2` with deterministic smoke-run outputs.
- Dominant risks: Python GIL interference with FastAPI concurrency and tighter coupling to the host process (crashes propagate). Mitigations include isolating heavy calls onto worker threads and retaining the subprocess adapter as a fallback.
- Next decision gate: capture full baseline vs rpy2 benchmarks once Redis-backed session persistence (Task 24) is in place so multi-tenant safety can be assessed.

### 8.4 Rollout Checklist

1. Promote warm pool changes through staging with smoke benchmarks before and after deploy; archive runs in `reports/perf/` alongside a brief summary.
2. Document runtime toggles (`ADAPTER_BACKEND`, `ADAPTER_TIMEOUT_MS`, job backend) in the deployment notes so operations can flip back to the cold subprocess path if stability issues arise.
3. For production, enable Prometheus histograms before widening the pool to capture any regression in `load_simulation` latency.

### 8.5 `/mcp/capabilities` Latency Budgets

Clients can query `/mcp/capabilities` to discover adapter metadata and timeouts. Example response in subprocess mode:

```json
{
  "transports": ["http-streamable"],
  "adapter": {
    "name": "subprocess",
    "populationSupported": true,
    "health": {
      "status": "initialised",
      "environment": {
        "available": false,
        "rPath": "/usr/local/bin/R",
        "ospsuiteLibs": null,
        "rVersion": "R version 4.2.3 (2023-03-15) -- \"Shortstop Beagle\"",
        "ospsuiteAvailable": false,
        "issues": []
      }
    }
  },
  "maxPayloadKb": 512,
  "timeouts": {
    "defaultMs": 300000,
    "adapterTimeoutMs": 30000
  },
  "annotations": {
    "service": "mcp-bridge",
    "environment": "development"
  }
}
```

- Update `adapterTimeoutMs` alongside benchmark artefacts whenever latency budgets change.
- Downstream agent clients should treat `adapter.name` (`subprocess`, `rpy2`, or future backends) as a hint to adjust retry timing and warm-up strategies.
