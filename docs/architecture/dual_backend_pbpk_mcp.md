# Dual-Backend PBPK MCP

## Status

Proposed target architecture, grounded in the current hybrid subprocess bridge and patch set in this workspace.

Current implementation signals:

- `scripts/ospsuite_bridge.R` already dispatches `.pkml` to `ospsuite` and `.R` to `rxode2`.
- `patches/mcp_bridge/adapter/ospsuite.py` already accepts both `.pkml` and `.R`.
- `patches/mcp/tools/load_simulation.py` already validates both `.pkml` and `.R`.

This document defines how to keep that flexibility without making the MCP harder to use.

## Product Positioning

The product should remain a single `PBPK_MCP`.

The implementation should support multiple execution backends behind one interface:

- `ospsuite` for PK-Sim / MoBi simulation-transfer files (`.pkml`)
- `rxode2` for custom and population-oriented `.R` model modules

`rxode2` should be presented as a first-class PBPK execution engine for native R-authored models, not merely as a landing zone for converted Berkeley Madonna projects.

Users should think in terms of a PBPK workflow, not server selection. The MCP should choose the backend from the model type and then report that choice explicitly.

For GitHub and public-facing docs, the positioning should be:

- accessible by default
  - one load / validate / run / results workflow regardless of backend
- explicit about scientific qualification
  - runnable models are not automatically qualified for risk assessment
- OECD-oriented for risk assessment use cases
  - context of use, applicability domain, uncertainty, verification, and peer-review status are first-class
- honest about format boundaries
  - PK-Sim / MoBi `.pkml` and MCP-ready `.R` are directly supported, Berkeley Madonna `.mmd` is a conversion source, not a runtime format

## Architecture Overview

```mermaid
flowchart TD
    user["User / Risk Assessor / Modeler"] --> api["PBPK_MCP API<br/>single user-facing workflow"]
    api --> load["load_simulation"]
    api --> validate["validate_simulation_request"]
    api --> run["run_simulation / run_population_simulation"]
    api --> results["get_job_status / get_results / get_population_results"]

    load --> router["Model Router<br/>select backend from model type"]
    router --> ospsuite["OSPSuite Backend<br/>PK-Sim / MoBi (.pkml)"]
    router --> rxode2["rxode2 Backend<br/>custom PBPK / population R (.R)"]

    ospsuite --> pkml[".pkml model files<br/>optional JSON profile sidecars"]
    rxode2 --> rmodels["MCP-ready R model modules<br/>self-declared model profile"]

    validate --> profile["Scientific Qualification Layer<br/>context of use / applicability domain / uncertainty / verification / review"]
    profile --> run

    mmadonna["Berkeley Madonna (.mmd)"] --> convert["Conversion Workflow"]
    convert --> pkml
    convert --> rmodels

    run --> det["Deterministic Results"]
    run --> pop["Population Results"]
    det --> results
    pop --> results
```

The important product message in that diagram is:

- the user sees one PBPK MCP
- backend selection is explicit but automatic
- OECD-style qualification sits beside execution, not hidden inside it
- unsupported source formats are handled through conversion, not silent runtime coercion

## Design Goals

- Keep one user-facing MCP surface.
- Preserve the clean PK-Sim / MoBi experience for `.pkml`.
- Add a first-class path for custom R-based PBPK models.
- Make backend differences explicit instead of hiding them.
- Allow backend-specific features without fragmenting the product.
- Support separate runtime images if dependency footprints diverge.

## Non-Goals

- Raw Berkeley Madonna `.mmd` execution.
- Pretending `.pkml` and `.R` models are internally identical.
- Forcing all backends to support the same advanced features.

## Key Rule

Unify the workflow, not the implementation.

That means:

- shared tool names for common tasks
- backend-specific capability flags
- explicit backend metadata on every loaded model and result
- clear capability errors when a tool is not supported for a model

## Supported Model Types

### Directly loadable

- `.pkml` via `ospsuite`
- `.R` via the PBPK R model-module contract

### Not directly loadable

- `.mmd`

Berkeley Madonna files should be treated as source artifacts that must be converted into either:

- `.pkml` for OSPSuite workflows, or
- `.R` for custom/R-based workflows

The MCP should never silently accept `.mmd` and then do ambiguous behavior.

## Canonical Concepts

### Model session

A loaded model instance tracked by `simulation_id`.

### Backend

The execution engine selected for the loaded model.

Initial backend values:

- `ospsuite`
- `rxode2`

### Deterministic result

A normal single-run simulation result with time-series output.

### Population result

A cohort simulation result with aggregate metrics and optional chunked subject-level payloads.

### Capability flags

A compact summary of what tools/behaviors the backend supports for that loaded model.

## Common Contract

Every loaded model should expose the same high-level handle shape:

```json
{
  "simulation_id": "cisplatin-rxode2",
  "file_path": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
  "metadata": {
    "name": "cisplatin_population_rxode2_model.R",
    "backend": "rxode2",
    "engine": "rxode2",
    "modelVersion": "2026-03-17",
    "createdBy": "rxode2",
    "createdAt": "2026-03-17T12:00:00Z"
  },
  "capabilities": {
    "supportsParameterEditing": true,
    "supportsDeterministicRuns": true,
    "supportsPopulationRuns": true,
    "supportsChunkedPopulationResults": true,
    "supportsUnitAwareParameters": false
  }
}
```

`capabilities` is the main addition that should be formalized next. The current patch set already returns `metadata.backend`; the next step is to expose capability flags alongside it.

The same loaded model should also be able to expose a scientific `profile` that is separate from operational `capabilities`:

```json
{
  "contextOfUse": {
    "regulatoryUse": "research-only"
  },
  "applicabilityDomain": {
    "qualificationLevel": "research-use"
  },
  "uncertainty": {
    "status": "partially-characterized"
  },
  "implementationVerification": {
    "status": "basic-internal-checks"
  },
  "peerReview": {
    "status": "not-reported"
  }
}
```

This separation is important because OECD-style scientific qualification is not the same thing as runtime support for a tool action.

## Tool Surface

### Common tools

These should remain shared across backends:

| Tool | Purpose | `ospsuite` | `rxode2` |
| --- | --- | --- | --- |
| `load_simulation` | Load a model by file path | Yes | Yes |
| `list_parameters` | Enumerate editable parameters | Yes | Yes |
| `get_parameter_value` | Read one parameter | Yes | Yes |
| `set_parameter_value` | Write one parameter | Yes | Yes |
| `run_simulation` | Run one deterministic simulation | Yes | Yes |
| `get_results` | Retrieve deterministic results | Yes | Yes |

### Backend-specific tools

These should exist only where they make sense:

| Tool | Purpose | `ospsuite` | `rxode2` |
| --- | --- | --- | --- |
| `run_population_simulation` | Run cohort/population workflow | No | Yes |
| `get_population_results` | Retrieve population results | No | Yes |

Future backend-specific tools should follow the same rule: shared if the semantics are truly shared, backend-specific if not.

## Behavioral Rules

### 1. Backend must be explicit

`load_simulation` must always report the selected backend.

### 2. Capability failures must be actionable

If a tool is called for an unsupported backend, return an explicit error such as:

```json
{
  "code": "capability_not_supported",
  "message": "Population simulations are not supported for backend 'ospsuite'",
  "details": {
    "backend": "ospsuite",
    "requiredCapability": "supportsPopulationRuns"
  }
}
```

### 3. Parameter paths stay canonical

Even if the implementation differs, parameter access should remain path-based from the MCP perspective.

### 4. Result types stay distinct

Deterministic results and population results should not be merged into one vague payload.

### 5. No silent format coercion

The MCP should not auto-convert `.mmd` or any other unsupported source format during `load_simulation`.

## Backend Capability Matrix

Initial capability model:

| Capability | Meaning | `ospsuite` | `rxode2` |
| --- | --- | --- | --- |
| `supportsParameterEditing` | Can edit model parameters through MCP | Yes | Yes |
| `supportsDeterministicRuns` | Can run one simulation and return time-series data | Yes | Yes |
| `supportsPopulationRuns` | Can run cohort sampling/simulation | No | Yes |
| `supportsChunkedPopulationResults` | Can return population chunks/handles | No | Yes |
| `supportsUnitAwareParameters` | Tool can reliably round-trip explicit units | Yes | Partial |
| `supportsEventTables` | Backend supports event-driven dosing tables | Partial | Future |

The exact capability list can grow, but it should stay small and operational.

## R Model-Module Contract

The current `.R` path should be formalized around this contract:

- `pbpk_model_metadata()`
- `pbpk_parameter_catalog()`
- `pbpk_default_parameters()`
- `pbpk_run_simulation(parameters, simulation_id = NULL, run_id = NULL, request = list())`
- `pbpk_run_population(parameters, cohort = list(), outputs = list(), simulation_id = NULL, request = list())`

Required behavior:

- `pbpk_default_parameters()` returns a named list
- parameter names are the canonical parameter paths
- deterministic results return normalized time-series payloads
- population results return aggregates plus optional chunk payloads

Recommended additions for the next revision:

- `pbpk_capabilities()`
- `pbpk_model_profile()`
- `pbpk_validate_request(request)`
- `pbpk_supported_outputs()`

Those additions would let the backend advertise richer behavior without leaking R implementation details into the MCP layer.

Recommended semantic split:

- `pbpk_capabilities()`
  - operational MCP behavior such as population-run support and parameter editing
- `pbpk_model_profile()`
  - scientific context-of-use, applicability domain, uncertainty, implementation verification, and peer-review metadata
- `pbpk_validate_request()`
  - request-level assessment that can report both runtime-guardrail failures and context-of-use mismatches

## Deployment Model

The user-facing MCP should stay unified even if the runtime splits.

Recommended topology:

- `pbpk-api`
  - one MCP/API surface
  - model routing
  - result persistence
- `pbpk-worker-ospsuite`
  - OSPSuite runtime and `.pkml` execution
- `pbpk-worker-rxode2`
  - R-heavy runtime with `rxode2` and related compiled dependencies

This is the preferred long-term shape because:

- OSPSuite and `rxode2` have different dependency and build profiles
- PK-Sim users should not pay for R-heavy runtime complexity if they do not need it
- `rxode2` source builds are memory-hungry and should be prebuilt into an image, not compiled inside a constrained runtime container

## User Experience Rules

To keep the MCP more usable rather than less usable:

- do not ask the user to choose a server
- do show the selected backend after load
- do keep common tools common
- do return capability-aware errors
- do document which model types are directly supported
- do not describe `.mmd` as directly executable

## Migration Plan

### Phase 1: Patch-based hybrid bridge

Status: mostly done in this workspace.

Deliverables:

- extension-based backend detection in `scripts/ospsuite_bridge.R`
- `.R` acceptance in `load_simulation`
- population-result persistence in the patched subprocess adapter
- one reference `rxode2` cisplatin model module

### Phase 2: Formalize shared response schemas

Deliverables:

- add `capabilities` to the model handle
- add `backend` and `engine` consistently to all result metadata
- standardize capability error codes
- document deterministic vs population result payloads

Acceptance criteria:

- every loaded model reports backend and capabilities
- unsupported tool calls fail with predictable capability errors

### Phase 3: Split runtime images, keep one MCP

Deliverables:

- dedicated OSPSuite worker image
- dedicated `rxode2` worker image with prebuilt R packages
- routing layer based on backend or model registry metadata

Acceptance criteria:

- PK-Sim workflows remain stable and low-friction
- R-heavy packages are no longer compiled inside constrained runtime workers

### Phase 4: Add model registry metadata

Deliverables:

- central registry of loadable models
- per-model backend declaration
- optional tags such as `renal`, `population`, `cisplatin`, `validated`

Acceptance criteria:

- tools can discover models without relying only on raw file paths
- the MCP can validate backend/model compatibility before load

Current implementation note:

- the workspace now has an initial filesystem-backed model registry surface via `/mcp/resources/models` and `discover_models`
- this discovery layer scans `MCP_MODEL_SEARCH_PATHS` for supported `.pkml` and `.R` files
- it is intentionally lightweight and path-based, so discovery does not require preloading every model at startup

### Phase 5: Berkeley Madonna conversion path

Deliverables:

- documented conversion workflow from `.mmd` to `.R` or `.pkml`
- optional helper script for extracting equations/parameters into the R model-module skeleton

Acceptance criteria:

- `.mmd` remains unsupported as a runtime format
- conversion into supported runtime formats becomes repeatable

## Recommended Near-Term Work

1. Add `capabilities` to the `load_simulation` response and adapter handle model.
2. Separate the worker image story from the MCP API story.
3. Prebuild an R worker image with `rxode2` rather than compiling inside the runtime worker.
4. Add a small model-registry layer so users can select named models instead of raw paths.
5. Treat Berkeley Madonna support as a conversion workflow, not a third execution backend.

## Decision Summary

The right architecture is:

- one `PBPK_MCP`
- multiple explicit execution backends
- one shared user workflow
- separate runtime images where needed

That keeps the system more usable, not less usable, because complexity stays in the backend boundary instead of the user interface.
