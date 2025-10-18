# Performance Profiling Notes

## Overview

This document captures the initial profiling pass for the MCP Bridge smoke
scenario and establishes a repeatable process for deeper investigations.

- **Harness:** `python -m mcp_bridge.benchmarking`
- **Dataset:** `tests/fixtures/demo.pkml`
- **Transport:** In-process ASGI (in-memory adapter)
- **Command:**

```bash
PYTHONPATH=src python -m mcp_bridge.benchmarking \
  --scenario smoke \
  --iterations 1 \
  --transport asgi \
  --simulation-file tests/fixtures/demo.pkml \
  --label dev-profile \
  --profile --profile-top 15
```

The run stores structured metrics in
`var/benchmarks/20251016T171028Z-smoke.json` and cProfile stats in
`var/benchmarks/profiles/20251016T171028Z-smoke.prof`.

## cProfile Highlights

Top cumulative time consumers (extracted from the JSON output):

| Rank | Function | Cumulative (s) | Notes |
| --- | --- | --- | --- |
| 1 | `base_events.py:_run_once` | 0.0457 | asyncio event loop dispatch; expected in ASGI mode. |
| 2 | `events.py:_run` | 0.0402 | httpx internal scheduler. |
| 3 | `cli.py:_run_smoke_iteration` (via `worker`) | 0.0260 | Benchmark orchestration of sequential tool calls. |
| 4 | `cli.py:post_json` → httpx client stack | ~0.026 | HTTP client round-trips dominate per-step latency. |
| … | FastAPI `applications.py:__call__` | 0.0214 | ASGI request lifecycle. |

**Observations**

1. The majority of time is spent in the asyncio/httpx stack, not in adapter or
   business logic, confirming that the in-memory adapter remains lightweight for
   the smoke tests.
2. `load_simulation` still accounts for ~25 ms wall time even with the in-memory
   adapter, highlighting file I/O and session registry setup. When R integration
   is enabled we should expect a larger share here.
3. No single function inside `mcp_bridge.adapter` or `JobService` appears in the
   top cumulative list, suggesting that adapter hotspots will only surface under
   heavier datasets or real subprocess usage.

**Immediate Actions**

- Re-run the profiler with `--iterations 10 --concurrency 4` after wiring the
  subprocess adapter to measure contention in the adapter bridge.
- Capture separate runs for `load_simulation`, `run_population_simulation`, and
  long-running jobs once stress datasets are available.

## py-spy / Flame Graph Workflow

Use `py-spy` for low-overhead sampling against either the in-process harness or
an externally running Uvicorn server. Example (ASGI transport shown for
consistency):

```bash
py-spy record \
  --format svg \
  --output var/benchmarks/flame-smoke.svg \
  --rate 200 \
  -- python3 -m mcp_bridge.benchmarking \
       --scenario smoke \
       --iterations 5 \
       --transport asgi \
       --simulation-file tests/fixtures/demo.pkml
```

Key tips:

- Run with the subprocess adapter (`--transport http` against a live server)
  when measuring R bridge costs; `py-spy` can attach to the Uvicorn PID rather
  than the harness process.
- Increase `--rate` (samples per second) for short benchmarks so flame graphs
  capture enough data; 200 Hz works well locally.
- Archive SVGs alongside JSON metrics under `var/benchmarks/flame/` for easy
  diff and historical comparisons.

## Next Steps

1. Integrate the profiler mode into CI smoke jobs (artifact upload only) and
   add thresholds once baseline variance is understood.
2. Schedule weekly py-spy sampling on the stress scenario to track regressions
   as the job system and adapter evolve.
3. Annotate hotspots inside adapter code with lightweight structlog timing logs
   (`logger.info("adapter.run_simulation", durationMs=...)`) to corroborate
   sampling data with in-app metrics.
