# Performance & Scalability Roadmap

This roadmap translates the benchmarking harness, profiling data, and prior
architecture research into concrete scaling actions for the MCP Bridge. It
should be reviewed alongside `performance-plan.md` and the profiling notes in
`performance-profiling.md`.

## 1. Baseline Observations (2025-10-16)

- `python -m mcp_bridge.benchmarking --scenario smoke --transport asgi` produces
  a 45–50 ms end-to-end wall time with a single iteration against the
  in-memory adapter.
- `load_simulation` dominates the smoke scenario (≈25 ms) even without invoking
  the subprocess adapter; expect significant increase once R integration is
  enabled.
- Profiling highlights asyncio/httpx overhead as the primary consumer of the
  runtime; adapter logic barely registers at smoke scale.
- No benchmarks exist yet for `run_population_simulation` or for subprocess
  adapter execution on actual `.pkml` assets larger than the demo fixture.

## 2. Short-Term Actions (Next 1–2 Sprints)

| Theme | Action | Owner/Notes |
| --- | --- | --- |
| Benchmark Coverage | Add Baseline/Stress datasets via `make fetch-bench-data` and wire CI smoke runs with `--profile`. | Task 19 follow-up; artifact upload in CI. |
| Adapter Insights | Enable structured timing logs in `SubprocessOspsuiteAdapter` (`logger.info("adapter.run_simulation", durationMs=...)`). | Leverages existing structlog wiring. |
| Async Tuning | Expose JobService thread count via env (already configurable) and document recommended values per workload tier. | Config docs + Makefile defaults. |
| Monitoring | Add Prometheus middleware (e.g., `prometheus-fastapi-instrumentator`) so the harness can scrape latency histograms during stress tests. | Optional flag in app factory. |

**Acceptance Criteria**

- Bench harness runs in CI (smoke) with profiling artefact stored under
  `var/benchmarks/`.
- Documentation updated with timing log guidance and JobService tuning knobs.

## 3. Medium-Term Scaling (2–6 Sprints)

### 3.1 Distributed Task Queue (Celery + RabbitMQ)

Trigger when:

- Concurrent simulation submissions exceed the thread pool capacity (≈4–8 jobs)
  or jobs routinely breach the 5 minute timeout.
- Need for persistent job state across process restarts.

Plan:

1. **Introduce Broker:** Add RabbitMQ (or Redis Streams) as a Celery broker and
   result backend. Containerize the stack for local dev (docker-compose).
2. **Refactor Submission:** Replace `JobService.submit_*` with thin wrappers that
   enqueue Celery tasks (`run_simulation_task.delay(...)`). Maintain API schema
   (job_id) by mapping Celery task IDs.
3. **Result Storage:** Adopt claim-check storage (S3/NAS) for large payloads; job
   record stores URI only (already supported by PopulationResultStore pattern).
4. **Observability:** Integrate Celery Flower or broker metrics export; update
   audit trail to log Celery task context (worker hostname, retry count).

### 3.2 Horizontal API Scaling

- Front the FastAPI app with a load balancer or Kubernetes Deployment once
  Celery externalizes long-running work.
- Use Uvicorn workers = `min(4, CPU cores)` with shared Redis cache for session
  registry so multiple API pods can access the same simulation handles.

**Acceptance Criteria**

- Benchmark harness supports `--transport http` targeting a Celery-backed API
  and records throughput scaling as worker count increases (1 → 4 workers shows
  near-linear submission throughput).
- Runbook added for broker maintenance and dead-letter queues.

## 4. Long-Term Scaling (HPC & Batch)

### 4.1 HPC Submission Pattern

Trigger when:

- Population simulations require thousands of core-hours, or regulations demand
  dedicated compute clusters.

Plan:

1. **Hybrid Worker:** Create a specialized Celery worker that submits jobs to
   Slurm/LSF via `sbatch` or similar; track external job_id alongside MCP job_id.
2. **State Synchronization:** Poll HPC scheduler for status, update MCP job
   records, and emit audit events for queue wait vs execution time.
3. **Data Management:** Stage input/output on shared object storage; use
   checksum validation hooks from the audit trail to confirm transfer integrity.
4. **Benchmark Harness:** Add an HPC scenario stub that records submission
   latency and eventual completion (mocked in CI, real in staging).

### 4.2 Batch & Spot Capacity

- Explore cloud spot fleets for non-critical workloads; integrate autoscaling
  policies with Celery worker pool using metrics (queue length, job age).
- Implement graceful drain logic so workers finish active simulations before
  termination.

## 5. Hardware Sizing Guidance

| Workload | Suggested Resources | Notes |
| --- | --- | --- |
| Dev / Smoke | 4 vCPU, 16 GB RAM, local SSD | Thread pool (2) sufficient; R optional. |
| Baseline | 8 vCPU, 32 GB RAM, NVMe | Celery optional; ensure R subprocess warm cache directory is on SSD. |
| Stress (population) | 16–32 vCPU, 64+ GB RAM, fast network to object storage | Celery + RabbitMQ required; consider GPU if leveraging ospsuite extensions (future). |
| HPC Submitter | 4 vCPU, 8 GB RAM on cluster login node | Low CPU needs; must access scheduler binaries. |

## 6. Observability & Regression Policy

- **Metrics:** Standardize on Prometheus (latency buckets, worker concurrency,
  broker queue depth). Add Grafana dashboards to track P95 vs targets.
- **Profiling Cadence:** Run cProfile + py-spy weekly on stress scenario; store
  flame graphs alongside JSON results.
- **Alerting:** Page on queue age > 2 minutes or job timeout > 2% of total runs.

## 7. Dependencies & Open Questions

- R subprocess initialization time must be benchmarked separately; consider
  pooling or `rpy2` migration if cold starts dominate.
- Session registry persistence (Redis) becomes mandatory once multiple API
  pods or Celery workers need shared state.
- Investigate ospsuite parallelization support to utilize multi-core or GPU
  enhancements in future releases.

---

**Revision log**

- *2025-10-16*: Initial roadmap drafted; captures current smoke metrics and
  lays out Celery/HPC strategy.
