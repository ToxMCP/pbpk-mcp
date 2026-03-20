# PBPK MCP Server

[![CI](https://github.com/ToxMCP/pbpk-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ToxMCP/pbpk-mcp/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.64898%2F2026.02.06.703989-blue)](https://doi.org/10.64898/2026.02.06.703989)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Release](https://img.shields.io/github/v/release/ToxMCP/pbpk-mcp?sort=semver)](https://github.com/ToxMCP/pbpk-mcp/releases)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

> Part of **ToxMCP** Suite → https://github.com/ToxMCP/toxmcp

**Public MCP endpoint for physiologically based pharmacokinetic (PBPK) simulation, qualification, and dossier export.**  
Expose PK-Sim / MoBi `.pkml`, MCP-ready `rxode2` `.R`, deterministic and population runs, and OECD-oriented validation/reporting to any MCP-aware agent (Codex CLI, Gemini CLI, Claude Code, etc.).

## Architecture

```mermaid
flowchart LR
    subgraph Clients["Clients and Agents"]
        Codex["Codex CLI / Desktop"]
        Gemini["Gemini CLI"]
        Claude["Claude Code"]
        Scripts["Scripts / notebooks"]
    end

    subgraph API["FastAPI MCP Service"]
        Router["HTTP entrypoints\n/health and /mcp"]
        Registry["Tool registry\npbpk-mcp.v1 contracts"]
        Tools["Tool handlers\ndiscovery, validation,\nexecution, reporting"]
    end

    subgraph Contracts["Discovery and Qualification Layer"]
        Catalog["Filesystem model catalog\nMCP_MODEL_SEARCH_PATHS"]
        Manifest["Static manifest validation\nvalidate_model_manifest"]
        Qualification["Qualification metadata\ncapabilities, profile,\nvalidation, qualificationState"]
        Reports["OECD dossier export\nexport_oecd_report"]
    end

    subgraph Backends["Execution Backends"]
        OSPSuite["OSPSuite backend\nPK-Sim / MoBi (.pkml)"]
        Rxode2["rxode2 backend\nMCP-ready R (.R)"]
        Convert["Conversion-only inputs\n.pksim5 and .mmd -> .pkml or .R"]
    end

    subgraph Runtime["Runtime and QA Path"]
        Jobs["Celery + Redis jobs\nasync runs and result handles"]
        Patches["Patch-first runtime\nshared patch manifest + installer"]
        Tests["Unit + live smoke tests\nrelease readiness checks"]
    end

    Clients --> Router
    Router --> Registry
    Registry --> Tools
    Tools --> Catalog
    Tools --> Manifest
    Tools --> Qualification
    Qualification --> Reports
    Tools --> OSPSuite
    Tools --> Rxode2
    Convert --> OSPSuite
    Convert --> Rxode2
    Tools --> Jobs
    Patches --> Tools
    Qualification --> Tests
    Patches --> Tests
```

The current implementation follows a layered model:

- `FastAPI + JSON-RPC` expose `/mcp` and `/health`, and keep transport concerns separate from PBPK model logic.
- `Tool handlers` are the agent-facing API. They validate inputs, call adapters, and emit structured responses with normalized `pbpk-mcp.v1` payloads.
- `Discovery and manifest validation` make model files visible before load, and keep curation checks separate from runtime execution.
- `Execution backends` route `.pkml` files to `ospsuite` and MCP-ready `.R` modules to `rxode2`, while treating `.pksim5` and `.mmd` as conversion-only inputs.
- `Qualification metadata` keeps `capabilities`, `profile`, `validation`, and `qualificationState` separate so runnable does not get conflated with scientifically qualified.
- `Patch-first runtime + smoke tests` keep the documented tool surface synchronized with the live API during the current `v0.3.0` convergence stage.

See `docs/architecture/dual_backend_pbpk_mcp.md` for the fuller architecture narrative, `docs/architecture/mcp_payload_conventions.md` for the response contract, and `docs/deployment/runtime_patch_flow.md` for the operator path behind the current local deployment model.

## What's new in v0.3.0

- Added discovery-first workflow coverage across `discover_models`, `/mcp/resources/models`, `validate_model_manifest`, `load_simulation`, `validate_simulation_request`, `run_simulation`, `get_results`, and `export_oecd_report`.
- Converged the live patch-first contract around a shared runtime patch manifest so the worker image and hot-patch flow apply the same runtime files.
- Tightened direct `.pksim5` and `.mmd` rejection with explicit conversion guidance instead of ambiguous runtime errors.
- Added live acceptance checks for `/mcp/list_tools`, `/mcp/resources/models`, and discovery/resource parity.
- Kept dual-backend execution explicit: `.pkml` loads on `ospsuite`; MCP-ready `.R` loads on `rxode2`.
- Preserved OECD-oriented reporting features such as `qualificationState`, `modelPerformance`, `parameterProvenance`, and `export_oecd_report`.

## Why this project exists

PBPK workflows often juggle PK-Sim or MoBi transfer files, R-authored mechanistic models, runtime-specific scripts, and incomplete qualification notes. That makes them difficult for coding agents to automate safely and difficult for reviewers to inspect consistently.

The PBPK MCP server wraps those workflows in a **single, programmable interface**:

- **Unified MCP surface** – discovery, manifest checks, load, validation, execution, results, and dossier export share one tool catalog.
- **Dual-backend execution** – `.pkml` models run on `ospsuite`; MCP-ready `.R` models run on `rxode2`.
- **Qualification-aware workflows** – runtime capability, scientific profile, preflight validation, and derived `qualificationState` stay separate.
- **Discovery before execution** – models are discoverable from disk before they are loaded into a live session.
- **Release-tested local deployment** – the patch-first runtime is continuously exercised with unit tests, live-stack tests, and a readiness check.

> `rxode2` is a native PBPK execution engine in this project. It is not limited to Berkeley Madonna conversion workflows.

---

## Feature snapshot

| Capability | Description |
| --- | --- |
| 🧬 **Dual-backend PBPK execution** | Route `.pkml` models to `ospsuite` and MCP-ready `.R` models to `rxode2` through one MCP surface. |
| 🗂️ **Model discovery and curation** | Discover supported model files from `MCP_MODEL_SEARCH_PATHS`, inspect unloaded models, and run static manifest checks before load. |
| 🛡️ **OECD-oriented qualification** | Keep `capabilities`, `profile`, `validation`, and `qualificationState` explicit; expose applicability, provenance, uncertainty, and qualification gaps. |
| 📈 **Deterministic and population jobs** | Submit asynchronous deterministic and population simulations, then retrieve result handles, stored results, and PK summaries. |
| 🧾 **Dossier export** | Export a structured OECD-style report with model metadata, validation context, checklist state, parameter provenance, and performance evidence when declared. |
| ⚙️ **Patch-first deployment hygiene** | Recreate the local stack and reapply the exact documented runtime patch set through shared patch-install tooling. |
| 🤖 **Agent friendly** | Verified through MCP HTTP surfaces such as `/mcp/list_tools`, `/mcp/call_tool`, and `/mcp/resources/models`, with live-stack regression checks. |

---

## Table of contents

1. [Architecture](#architecture)
2. [Quick start](#quick-start)
3. [Configuration](#configuration)
4. [Tool catalog](#tool-catalog)
5. [Running the server](#running-the-server)
6. [Integrating with coding agents](#integrating-with-coding-agents)
7. [Output artifacts](#output-artifacts)
8. [Security checklist](#security-checklist)
9. [Current limitations](#current-limitations)
10. [Development notes](#development-notes)
11. [Contributing](#contributing)
12. [Security policy](#security-policy)
13. [Code of conduct](#code-of-conduct)
14. [Citation](#citation)
15. [Roadmap](#roadmap)
16. [License](#license)

---

## Quickstart TL;DR

```bash
# 1) build the worker image
git clone https://github.com/ToxMCP/pbpk-mcp.git
cd pbpk-mcp

# 2) start the local stack
./scripts/build_rxode2_worker_image.sh
./scripts/deploy_rxode2_stack.sh

# 3) verify
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/mcp/list_tools | jq '.tools[].name'
```

## Quick start

```bash
git clone https://github.com/ToxMCP/pbpk-mcp.git
cd pbpk-mcp

./scripts/build_rxode2_worker_image.sh
./scripts/deploy_rxode2_stack.sh
```

> **Heads-up:** The current local deployment is intentionally patch-first. `./scripts/deploy_rxode2_stack.sh` recreates the stack and reapplies the current runtime patch set so the live API matches the documented `v0.3.0` contract.

Once the server is running:

- HTTP MCP endpoint: `http://localhost:8000/mcp`
- Health check: `http://localhost:8000/health`
- Model discovery resource: `http://localhost:8000/mcp/resources/models`
- Architecture docs: `docs/architecture/dual_backend_pbpk_mcp.md`
- Runtime operator docs: `docs/deployment/runtime_patch_flow.md`

## Verification (smoke test)

Once the server is running:

```bash
# health
curl -s http://localhost:8000/health | jq .

# list MCP tools
curl -s http://localhost:8000/mcp/list_tools | jq .

# discover cisplatin
curl -s -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{"tool":"discover_models","arguments":{"search":"cisplatin","limit":10}}' | jq .

# static manifest validation
curl -s -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{"tool":"validate_model_manifest","arguments":{"filePath":"/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R"}}' | jq .
```

For the full live-stack gate, run:

```bash
python3 scripts/release_readiness_check.py
```

---

## Configuration

The default local stack is defined in `docker-compose.celery.yml`. Key environment variables currently shaping the runtime are:

| Variable | Default | Description |
| --- | --- | --- |
| `MCP_MODEL_SEARCH_PATHS` | `/app/var` | Filesystem roots scanned by `discover_models` and `/mcp/resources/models`. |
| `ADAPTER_BACKEND` | `subprocess` | Uses the R / OSPSuite subprocess bridge instead of an in-memory mock path. |
| `JOB_BACKEND` | `celery` | Enables asynchronous job submission through Redis-backed Celery workers. |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Queue broker for asynchronous jobs. |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Result storage for job handles and async result chaining. |
| `R_PATH` / `R_HOME` | container defaults | Point the bridge to the R runtime used by `rxode2` and OSPSuite tooling. |
| `R_MAX_VSIZE` | `2G` | Caps R virtual memory use inside the current local worker setup. |
| `DOTNET_GCHeapLimitPercent` | `60` | Constrains the .NET heap used by the OSPSuite runtime. |
| `SERVICE_VERSION` | `0.3.0` | Exposed through `/health` and compose-level runtime metadata. |
| `AUTH_ALLOW_ANONYMOUS` | `true` | Development-friendly local default; do not expose beyond localhost without hardening. |

See `docker-compose.celery.yml`, `docs/deployment/runtime_patch_flow.md`, and `docs/deployment/rxode2_worker_image.md` for the current operator-facing deployment surface.

---

## Tool catalog

| Category | Highlight tools | Notes |
| --- | --- | --- |
| Discovery and curation | `discover_models`, `validate_model_manifest`, `load_simulation` | Discover models before load, inspect static manifest state, and load supported `.pkml` or MCP-ready `.R` files into the live session registry. |
| Qualification and reporting | `validate_simulation_request`, `export_oecd_report` | Run OECD-oriented preflight checks and export structured dossiers with `profile`, `validation`, `qualificationState`, and evidence sections. |
| Simulation control | `list_parameters`, `get_parameter_value`, `set_parameter_value`, `run_simulation` | Inspect and modify simulation parameters, then submit deterministic runs asynchronously. |
| Async status and results | `get_job_status`, `get_results`, `calculate_pk_parameters`, `cancel_job` | Track async jobs, retrieve stored deterministic results, compute PK summaries, and cancel queued/running jobs. |
| Population and exploration | `run_population_simulation`, `get_population_results`, `run_sensitivity_analysis` | Run population workflows and sensitivity analyses on the backends that declare those capabilities. |

The normalized `pbpk-mcp.v1` contract currently applies to:

- `load_simulation`
- `validate_model_manifest`
- `validate_simulation_request`
- `export_oecd_report`
- `get_job_status`
- `get_results`

### Example workflow

For the current public workflow:

1. Call `discover_models` or inspect `/mcp/resources/models`.
2. Call `validate_model_manifest` before loading a new model.
3. Call `load_simulation`.
4. Call `validate_simulation_request` for the intended context of use.
5. Submit `run_simulation` or `run_population_simulation`.
6. Poll `get_job_status`, then fetch `get_results` or `get_population_results`.
7. Call `export_oecd_report` when you need a dossier/report package.

### Supported model policy

Supported runtime inputs:

- `.pkml` via `ospsuite`
- MCP-ready `.R` via `rxode2`

Conversion-only inputs:

- `.pksim5` PK-Sim project files
- Berkeley Madonna `.mmd`

Both conversion-only formats are rejected early with explicit guidance to export to `.pkml` or convert to an MCP-ready `.R` model.

Qualification model:

PBPK MCP keeps these concepts separate:

- `capabilities` for operational/runtime support
- `profile` for declared scientific metadata
- `validation` for preflight applicability and guardrail assessment
- `qualificationState` for the derived summary label

Current derived qualification states include:

- `exploratory`
- `illustrative-example`
- `research-use`
- `regulatory-candidate`
- `qualified-within-context`

This is the core policy boundary for the server:

- executable does not mean qualified
- in-bounds does not mean suitable for regulatory use

For `.R` models, richer OECD-oriented reporting is enabled by hooks such as:

- `pbpk_model_profile()`
- `pbpk_validate_request(...)`
- `pbpk_parameter_table(...)`
- `pbpk_performance_evidence(...)`

For `.pkml` models, richer qualification metadata can be supplied with sidecars such as:

- `model.profile.json`
- `model.pbpk.json`

---

## Running the server

The default local stack is:

- `pbpk_mcp-api-1` on `http://127.0.0.1:8000`
- `pbpk_mcp-worker-1` on the same `pbpk_mcp-worker-rxode2:latest` image for execution
- `pbpk_mcp-redis-1` for job brokering and result storage

The preferred local operator entrypoint is:

```bash
./scripts/deploy_rxode2_stack.sh
```

That command recreates the containers and reapplies the current runtime patch set so the live tool catalog remains aligned with the documented contract.

---

## Integrating with coding agents

Add `http://localhost:8000/mcp` as an MCP provider in Codex CLI/Desktop, Gemini CLI, Claude Code, or other MCP-aware hosts.

Useful companion surfaces:

- `/mcp/list_tools` for the live tool catalog
- `/mcp/call_tool` for direct HTTP tool execution
- `/mcp/resources/models` for discoverable model files
- `/mcp/resources/simulations` for already-loaded live sessions

Critical tools still declare MCP-side guardrails such as `critical` and `requiresConfirmation` in the tool catalog. The current live regression suite checks that the documented workflow is actually exposed through `/mcp/list_tools`.

---

## Output artifacts

The server currently produces and exposes:

- discovered model inventories with loaded/unloaded state
- static manifest validation reports
- load-time model metadata with `backend`, `capabilities`, `profile`, `validation`, and `qualificationState`
- deterministic result handles and stored deterministic result payloads
- population summary payloads and chunk handles
- PK metric outputs from `calculate_pk_parameters`
- OECD-style dossier/report exports with checklist state, missing-evidence hints, performance evidence, and parameter provenance when declared

---

## Security checklist

- ✅ Dual-backend runtime policy is explicit: `.pkml` and MCP-ready `.R` are supported; `.pksim5` and `.mmd` are conversion-only.
- ✅ Discovery, manifest validation, runtime validation, and OECD dossier export are exposed as separate tool surfaces.
- ✅ `capabilities`, `profile`, `validation`, and `qualificationState` remain distinct, so runtime support is not mislabeled as scientific qualification.
- ✅ The shared runtime patch manifest keeps image builds and hot-patch deployment aligned in the current patch-first stage.
- ✅ Live readiness checks verify `/mcp/list_tools`, `/mcp/resources/models`, discovery parity, and conversion-only rejection behavior.
- 🔲 The default local compose stack is still development-oriented; harden auth and ingress before exposing it beyond localhost.
- 🔲 Qualification evidence completeness still depends on the model or sidecar; executable does not imply regulatory readiness.

## Current limitations

### Format and backend limitations

- Raw Berkeley Madonna `.mmd` files are not directly executable.
- Only `.pkml` and MCP-ready `.R` are supported runtime formats.
- PK-Sim / MoBi project files such as `.pksim5` are not loaded directly and must be exported to `.pkml`.
- An `.R` file can be discoverable without being runnable if it does not implement the required contract.
- Backend capabilities are intentionally not identical across `ospsuite` and `rxode2`.
- Population simulation is currently implemented for `rxode2` models, not as a generic OSPSuite `.pkml` capability.

### Qualification limitations

- `validate_model_manifest` is a static pre-load check; it does not by itself prove executable correctness or scientific validity.
- Runtime guardrails are not the same as external scientific validation.
- `research-use` or `illustrative-example` models should not be represented as regulatory-ready.
- OECD-style metadata completeness can be high while scientific evidence remains incomplete.
- Exported `performanceEvidence` may still reflect runtime or smoke-test evidence rather than observed-versus-predicted qualification datasets.
- Parameter provenance may be structured and exportable while still lacking full per-parameter citations, study conditions, or identifiability evidence.

### Operational limitations

- `rxode2` image builds are heavy and should be prebuilt rather than compiled inside a capped runtime worker.
- Runtime workers should stay conservatively capped, such as `4 GiB`.
- Durable `rxode2` image builds can take a long time on laptop hardware because of C/C++ compilation.
- The current local deployment is patch-first, so container recreate should be followed by the shared patch-install flow to keep the live API aligned with the current workspace contract.

---

## Development notes

Recommended checks:

```bash
python3 -m unittest -v tests/test_load_simulation_contract.py
python3 -m unittest -v tests/test_model_manifest.py
python3 -m unittest -v tests/test_oecd_bridge.py
python3 -m unittest -v tests/test_model_discovery_live_stack.py
python3 -m unittest -v tests/test_oecd_live_stack.py
python3 scripts/release_readiness_check.py
```

### Maintainer workflow

If you are maintaining the local stack in the current convergence stage:

1. Change the authoritative runtime files in `patches/`, `scripts/ospsuite_bridge.R`, or the bundled `.R` model modules.
2. If the worker image baseline should change, rebuild it with `./scripts/build_rxode2_worker_image.sh`.
3. Recreate the stack with `./scripts/deploy_rxode2_stack.sh`.
4. Verify the live API with:
   - `curl -s http://localhost:8000/health`
   - `curl -s http://localhost:8000/mcp/list_tools`
   - `python3 scripts/release_readiness_check.py`

Important boundaries:

- `scripts/deploy_rxode2_stack.sh` is the preferred local operator entrypoint.
- `scripts/apply_rxode2_patch.py` is the lower-level recovery tool if you need to reapply the current contract without a full recreate.
- `scripts/install_runtime_patches.py` and `scripts/runtime_patch_manifest.py` define the shared patch set used by both the worker image build and the runtime patch flow.
- `patches/` is still the canonical implementation layer for the current `v0.3.0` stage; pure `src/` packaging migration is intentionally deferred.

### Useful repository guideposts

- `scripts/ospsuite_bridge.R`
- `scripts/runtime_patch_manifest.py`
- `scripts/install_runtime_patches.py`
- `scripts/apply_rxode2_patch.py`
- `patches/mcp_bridge/model_catalog.py`
- `patches/mcp_bridge/model_manifest.py`
- `patches/mcp/tools/discover_models.py`
- `patches/mcp/tools/validate_model_manifest.py`
- `patches/mcp/tools/validate_simulation_request.py`
- `docs/architecture/dual_backend_pbpk_mcp.md`
- `docs/deployment/runtime_patch_flow.md`
- `docs/integration_guides/rxode2_adapter.md`
- `docs/integration_guides/ospsuite_profile_sidecars.md`
- `docs/github_publication_checklist.md`

---

## Contributing

Use the clean GitHub clone as the release source of truth when publishing. Before proposing a release or publication update, run the readiness checks above and review the publication checklist in `docs/github_publication_checklist.md`.

For the published repo, follow `CONTRIBUTING.md`.

---

## Security policy

The default local compose stack is development-oriented and currently allows anonymous local use. Do not expose it beyond localhost without hardening authentication, ingress, and runtime resource limits.

For the published repo, follow `SECURITY.md`.

---

## Code of conduct

Community interactions for the published repo should follow `CODE_OF_CONDUCT.md`.

---

## Citation

If you use PBPK MCP in your work, please cite the BioRxiv preprint:

Djidrovski, I. **ToxMCP: Guardrailed, Auditable Agentic Workflows for Computational Toxicology via the Model Context Protocol.** bioRxiv (2026). https://doi.org/10.64898/2026.02.06.703989

```bibtex
@article{djidrovski2026toxmcp,
  title   = {ToxMCP: Guardrailed, Auditable Agentic Workflows for Computational Toxicology via the Model Context Protocol},
  author  = {Djidrovski, Ivo},
  journal = {bioRxiv},
  year    = {2026},
  doi     = {10.64898/2026.02.06.703989},
  url     = {https://doi.org/10.64898/2026.02.06.703989}
}
```

Citation metadata: `CITATION.cff`

---

## Roadmap

- Move from the current patch-first convergence stage into a packaged `src/` implementation once the public contract is fully stable.
- Add richer quantitative uncertainty, sensitivity, and implementation-verification evidence to strengthen regulatory-facing qualification.
- Expand dossier-grade parameter provenance and model-performance evidence across curated example and production models.
- Keep improving release automation so image build, hot patching, docs, and version markers stay aligned.

---

## License

Apache-2.0
