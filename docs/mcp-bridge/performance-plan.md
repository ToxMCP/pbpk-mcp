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
- Add a `make fetch-bench-data` target to download or validate Baseline/Stress assets.
- CI quality workflow now runs `make benchmark` and uploads the latest smoke JSON artefact for regression tracking.
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

## 7. Acceptance Gates and Regression Policy

- A change fails CI if any tracked metric regresses by more than 15% over the Baseline tier targets or exceeds absolute limits in Section 4.
- Stress tier runs weekly; if completion time exceeds `≤ 12 min` by >10%, task owner opens a follow-up issue with profiling artifacts.
- Cold-start `load_simulation` must stay below 5 s even on constrained developer laptops (4 vCPU / 16 GB RAM); warn (but do not block) if it rises above 3.5 s.
- Throughput targets for `get_population_results` assume local filesystem; when object storage is enabled, update thresholds but retain ≥ 30 MB/s minimum.
- Any manual Extreme tier assessment must end with a short summary committed under `reports/perf/` describing scaling recommendations and environment details.
