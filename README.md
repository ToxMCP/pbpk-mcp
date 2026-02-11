[![CI](https://github.com/ToxMCP/pbpk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ToxMCP/pbpk-mcp/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.64898%2F2026.02.06.703989-blue)](https://doi.org/10.64898/2026.02.06.703989)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Release](https://img.shields.io/github/v/release/ToxMCP/pbpk-mcp?sort=semver)](https://github.com/ToxMCP/pbpk-mcp/releases)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

# PBPK MCP Server

> Part of **ToxMCP** Suite → https://github.com/ToxMCP/toxmcp


**Public MCP endpoint for physiologically based pharmacokinetic (PBPK) modeling with Open Systems Pharmacology Suite.**  
Expose deterministic/population simulations, parameter edits, and PK analytics to any MCP-aware agent (Codex CLI, Gemini CLI, Claude Code, etc.).

## Why this project exists

PBPK workflows typically juggle `.pkml` and `.pksim5` models, ospsuite tooling, and ad-hoc scripts that are hard for coding agents to automate safely. The PBPK MCP server wraps those workflows in a **secure, programmable interface**:

- **Single MCP surface** for loading models, editing parameters, running simulations, and computing PK metrics.
- **Adapter flexibility** – in-memory adapter for fast local work; subprocess adapter to call R/ospsuite when you need full fidelity.
- **Job safety** – confirmation gating for critical tools, idempotency keys for reruns, and persistent job registry with cancellation.
- **Audit + observability** – immutable audit chain, Prometheus metrics, and parity/benchmark harnesses to guard regressions.

---

## Feature snapshot

| Capability | Description |
| --- | --- |
| 🧬 **PBPK simulation control** | Load `.pkml` and `.pksim5` models, list/edit parameters, and run deterministic or population simulations via MCP tools. |
| 🧾 **PK analytics** | Compute Cmax/Tmax/AUC on completed runs; retrieve aggregated population results and chunk handles. |
| 🔁 **Job orchestration & idempotency** | Async job service with idempotency keys, cancellation, and persistent registry (thread, Celery, or HPC stub backends). |
| 🛡️ **Guardrails by default** | Critical tools require explicit confirmation; role annotations and JSON Schemas are returned in the tool catalog. |
| 📈 **Observability** | Structured logs, audit bundles, `/metrics` (Prometheus), and benchmark/parity suites baked into the repo. |
| 🤖 **Agent friendly** | MCP HTTP endpoints expose `list_tools`, `call_tool`, and capability data; smoke scripts and integration snippets are included. |

---

## Table of contents

1. [Quick start](#quick-start)
2. [Real-World Examples](#real-world-examples)
3. [Configuration](#configuration)
4. [Tool catalog](#tool-catalog)
5. [Running the server](#running-the-server)
6. [Integrating with coding agents](#integrating-with-coding-agents)
7. [Output artifacts](#output-artifacts)
8. [Security checklist](#security-checklist)
9. [Development notes](#development-notes)
10. [Roadmap](#roadmap)
11. [Citation](#citation)
12. [License](#license)

---

## Quick start (Docker)

The easiest way to run the server with the **Real Physics Engine (OSPSuite/R)** is via Docker Compose.

```bash
git clone https://github.com/senseibelbi/PBPK_MCP.git
cd PBPK_MCP

# Create necessary directories
mkdir -p var/jobs var/population-results

# Copy example environment
cp .env.example .env

# Start the API and Worker with R support
docker compose -f docker-compose.celery.yml up -d --build
```

- **API Endpoint:** `http://localhost:8000/mcp`
- **Worker:** Handles simulation jobs using the installed R runtime.
- **Models:** Place your `.pkml` or `.pksim5` files in `var/`. (Acetaminophen_Pregnancy.pkml is auto-downloaded in some setups).

## Real-World Examples

We provide a comprehensive suite of examples in the `examples/` directory demonstrating full workflows against the real engine:

1.  **Brain Barrier Distribution:** Checks if a drug crosses the BBB by comparing Brain vs Blood AUC.
2.  **Sensitivity Analysis:** Sweeps physiological parameters (e.g., Liver Volume) to assess impact on clearance.
3.  **Virtual Population:** Simulates a cohort with varying physiology.
4.  **Automated Sensitivity Tool:** Demonstrates the high-level `run_sensitivity_analysis` tool.

To run the examples (requires Python requests):

```bash
python3 examples/01_brain_barrier_distribution.py
python3 examples/02_liver_volume_sensitivity.py
python3 examples/06_sensitivity_tool_demo.py
```

See `examples/README.md` for details.

---

## Model Conversion (.pksim5 to .pkml)

The MCP server natively loads `.pkml` simulation files. To use `.pksim5` PK-Sim projects:

1.  **Manual Export:** Open the project in PK-Sim, right-click the simulation, and "Export to PKML...".
2.  **Automated Conversion (Linux/Windows):** Use the included helper script in an environment with the `ospsuite` R package (e.g., the Docker container).

```bash
Rscript scripts/convert_pksim_to_pkml.R path/to/project.pksim5 output/directory
```

This pipeline converts the project to a JSON snapshot and then exports the `.pkml` simulation(s).

## Configuration

Settings are loaded via `pydantic` models plus `python-dotenv` `.env` loading. Common knobs (see `docs/mcp-bridge/reference/configuration.md` for the full matrix):

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `HOST` | Optional | `0.0.0.0` | Bind address for the FastAPI app. |
| `PORT` | Optional | `8000` | HTTP port. |
| `ADAPTER_BACKEND` | Optional | `inmemory` | Switch to `subprocess` to use R/ospsuite (Docker default). |
| `MCP_MODEL_SEARCH_PATHS` | Optional | `tests/fixtures` | Colon-separated allow list of model directories. |
| `ADAPTER_TIMEOUT_MS` | Optional | `30000` | Adapter call timeout. |
| `JOB_BACKEND` | Optional | `thread` | `thread`, `celery`, or `hpc` (stub) for testing agent interactions with queued cluster jobs. |
| `JOB_WORKER_THREADS` | Optional | `2` | In-process worker pool size. |
| `JOB_TIMEOUT_SECONDS` | Optional | `300` | Per-job timeout for queued executions. |
| `JOB_REGISTRY_PATH` | Optional | `var/jobs/registry.json` | Persistent job registry for status checks/idempotency. |
| `AUTH_DEV_SECRET` | Dev | – | HS256 secret for local tokens (set issuer/audience values for production JWT validation). |
| `AUDIT_ENABLED` | Optional | `true` | Toggle immutable audit logging. |
| `AUDIT_STORAGE_BACKEND` | Optional | `local` | `local` JSONL logs or `s3` with Object Lock (`AUDIT_S3_*`). |
| `LOG_LEVEL` | Optional | `INFO` | Structured log verbosity. |
| `ENVIRONMENT` | Optional | `development` | Environment banner used in `/health` and logs. |

---

## Tool catalog

| Tool | Description |
| --- | --- |
| `load_simulation` | Load a PBPK `.pkml` or `.pksim5` file into the session registry (critical; requires confirmation). |
| `list_parameters` | List parameter paths for a loaded simulation (supports glob filters). |
| `get_parameter_value` | Retrieve the current value for a simulation parameter. |
| `set_parameter_value` | Update a parameter with optional unit/comment (critical; requires confirmation). |
| `run_simulation` | Submit an asynchronous deterministic simulation and receive a job handle (supports `idempotencyKey`). |
| `get_job_status` | Inspect the status/result of a submitted job. |
| `calculate_pk_parameters` | Compute PK metrics (Cmax, Tmax, AUC) for a completed simulation result. |
| `run_population_simulation` | Execute a population simulation asynchronously and return a job handle (supports `idempotencyKey`). |
| `get_population_results` | Fetch aggregated results and chunk handles for a population run. |
| `cancel_job` | Request cancellation of a queued or running job. |
| `run_sensitivity_analysis` | Run a multi-parameter sensitivity analysis workflow and return PK deltas (critical; requires confirmation). |

Each tool in `list_tools` returns JSON Schemas plus annotations for `roles`, `critical`, and `requiresConfirmation` to help agents enforce guardrails client-side.

---

## Running the server

### Local development (Python only)

```bash
# in-memory adapter (no R), with development JWTs
export AUTH_DEV_SECRET=dev-secret
export ADAPTER_BACKEND=inmemory
export MCP_MODEL_SEARCH_PATHS=$(pwd)/tests/fixtures
uvicorn mcp_bridge.main:app --host 0.0.0.0 --port 8000 --reload
```

### Quick MCP smoke test

```bash
BASE_URL=http://localhost:8000
AUTH_HEADER="Authorization: Bearer $(PYTHONPATH=src python - <<'PY'
from mcp_bridge.security.simple_jwt import jwt
print(jwt.encode({"sub": "smoke", "roles": ["admin"]}, "dev-secret", algorithm="HS256"))
PY
)"

# Tool discovery
curl -s "$BASE_URL/mcp/list_tools" -H "$AUTH_HEADER" | jq '.tools | length'

# Load demo model and run a deterministic simulation
curl -s -X POST "$BASE_URL/mcp/call_tool" \
  -H "Content-Type: application/json" -H "$AUTH_HEADER" \
  -d '{"tool":"load_simulation","arguments":{"filePath":"tests/fixtures/demo.pkml","simulationId":"smoke"},"critical":true}' | jq '.structuredContent.simulationId'

curl -s -X POST "$BASE_URL/mcp/call_tool" \
  -H "Content-Type: application/json" -H "$AUTH_HEADER" \
  -d '{"tool":"run_simulation","arguments":{"simulationId":"smoke"},"critical":true,"idempotencyKey":"smoke-1"}' | jq '.structuredContent.jobId'
```

Use `scripts/mcp_http_smoke.sh` for a scripted handshake and CLI walkthroughs in `docs/mcp-bridge/getting-started/` for REST + agent flows.

---

## Integrating with coding agents

- Add `http://localhost:8000/mcp` as an MCP provider (Codex CLI, Gemini CLI, Claude Code, or other hosts).
- Include `Authorization: Bearer <token>` and set `critical: true` in payloads for critical tools (legacy `X-MCP-Confirm: true` is also honoured).
- When an agent calls a critical tool, the server will respond with a `confirmationRequired` status. The agent must then re-submit the request with a confirmation token or signal.
- Reference `docs/mcp-bridge/integration_guides/mcp_integration.md` for client-specific JSON snippets and binary payload handling.

---

## Output artifacts

- **Structured MCP payloads** – responses include `content` plus `structuredContent` with job handles, simulation IDs, PK metrics, and population result metadata.
- **Audit + provenance** – critical tool invocations record digests, argument keys, and identities; optional S3 Object Lock storage keeps the chain immutable.
- **Metrics** – `/metrics` exposes MCP tool latency/histograms and HTTP counters suitable for Prometheus/Grafana (see `docs/monitoring/`).
- **Benchmarks** – smoke/parity benchmark JSON artefacts land in `var/benchmarks/` for regression checks.

---

## Security checklist

- ✅ Require auth in production (`AUTH_ISSUER_URL`/`AUTH_AUDIENCE` or gateway enforcement); use `AUTH_DEV_SECRET` only for local work.
- ✅ Critical tools enforce explicit confirmation and audit logging.
- ✅ Idempotency keys deduplicate simulation submissions; job registry persists across restarts.
- ✅ Limit model search paths (`MCP_MODEL_SEARCH_PATHS`) and memory-intensive backends when running on constrained hosts.
- 🔲 Harden ingress (TLS, rate limits) and align RBAC with your deployment before exposing beyond localhost.

---

## Development notes

- `make lint` / `make type` / `make test` – fast quality gates; `make test-e2e` and `make parity` run heavier suites.
- `make benchmark` – smoke benchmark (in-process) with optional profiling via `BENCH_PROFILE=1`.
- `make goldset-eval` – validate literature extraction quality against the gold set.
- `make build-image` / `make run-image` – container workflow; `docker-compose.celery.yml` spins up API + Redis + Celery stub.
- Distributed execution: set `JOB_BACKEND=celery` or `JOB_BACKEND=hpc` (stub Slurm) and follow the runbooks in `docs/operations/`.
- Agent scaffolds: `run_agent.py demo` exercises the confirm-before-execute loop using the in-memory adapter.

---

## Roadmap

- Streaming progress updates for long-running simulations and population jobs.
- Expanded parity/benchmark scenarios covering additional reference models and sensitivity profiles.
- Optional SSE/WebSocket transport for MCP once the spec finalizes streaming semantics.

---

## Citation

If you use **toxMCP / PBPK MCP** in your work, please cite the BioRxiv preprint:

- Author: **Ivo Djidrovski**
- Link: [https://www.biorxiv.org/content/10.64898/2026.02.06.703989v1](https://www.biorxiv.org/content/10.64898/2026.02.06.703989v1)

---

## License

This project is distributed under the [Apache License 2.0](LICENSE). Contributions are accepted under the same terms.
## Acknowledgements / Origins

ToxMCP was developed in the context of the **VHP4Safety** project (see: https://github.com/VHP4Safety) and related research/engineering efforts.

Funding: Dutch Research Council (NWO) — NWA.1292.19.272 (NWA programme)

This suite integrates with third-party data sources and services (e.g., EPA CompTox, ADMETlab, AOP resources, OECD QSAR Toolbox, Open Systems Pharmacology). Those upstream resources are owned and governed by their respective providers; users are responsible for meeting any access, API key, rate limit, and license/EULA requirements described in each module.

## Cite

If you use ToxMCP in your work, please cite the preprint: https://doi.org/10.64898/2026.02.06.703989

Citation metadata: [CITATION.cff](./CITATION.cff)
