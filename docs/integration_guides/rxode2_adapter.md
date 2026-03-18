# rxode2 Adapter Workflow

For the broader product architecture and rollout plan, see:

- `docs/architecture/dual_backend_pbpk_mcp.md`
- `docs/deployment/rxode2_worker_image.md`

This workspace now includes a hybrid subprocess bridge that can handle both:

- OSPSuite simulation transfer files (`.pkml`)
- `rxode2` model modules (`.R`)

The `rxode2` path is a direct execution backend for PBPK models authored natively in R. It is not restricted to models converted from Berkeley Madonna.

## Files added for the rxode2 path

- `scripts/ospsuite_bridge.R`
  - Hybrid bridge process used by the Python adapter.
- `cisplatin_models/cisplatin_population_rxode2_model.R`
  - MCP-friendly cisplatin `rxode2` model module.
- `patches/mcp_bridge/adapter/ospsuite.py`
  - Patched subprocess adapter with `.R` support and population result persistence.
- `patches/mcp/tools/load_simulation.py`
  - Patched tool validation so `.R` model modules are accepted.
- `scripts/apply_rxode2_patch.py`
  - Copies the patched files into the live PBPK MCP container.

## Expected rxode2 model-module contract

Each model file loaded through the bridge should define:

- `pbpk_model_metadata()`
- `pbpk_model_profile()`
- `pbpk_parameter_catalog()`
- `pbpk_default_parameters()`
- `pbpk_run_simulation(parameters, simulation_id = NULL, run_id = NULL, request = list())`
- `pbpk_run_population(parameters, cohort = list(), outputs = list(), simulation_id = NULL, request = list())`

Optional guardrail hooks:

- `pbpk_supported_outputs()`
- `pbpk_capabilities()`
- `pbpk_validate_request(request = list(), parameters = NULL, stage = NULL, ...)`

The bridge keeps parameter editing generic, so parameter values are stored by path in the bridge and passed into the model functions as a named list.

If `pbpk_capabilities()` is present, its payload is surfaced through `load_simulation`.
If `pbpk_model_profile()` is present, `load_simulation` also returns a `profile` block with OECD-style scientific metadata such as:

- `contextOfUse`
- `applicabilityDomain`
- `uncertainty`
- `implementationVerification`
- `peerReview`

If `pbpk_validate_request()` is present, the bridge calls it during:

- `load_simulation`
- `set_parameter_value`
- `run_simulation`
- `run_population_simulation`

Validation errors are returned before execution as adapter `InteropError`s with the normalized field-level messages from the model hook.

Current convention:

- `capabilities` reports operational MCP behavior
- `profile` reports scientific/context-of-use metadata
- `validation.assessment` explains whether the request is only inside runtime guardrails or actually backed by stronger qualification evidence

Current MCP surfaces that use this data:

- `load_simulation`
  - returns `capabilities`, `profile`, and the default `validation` payload for the loaded model
- `validate_simulation_request`
  - runs preflight validation without triggering execution
- `run_simulation` / `get_results`
  - preserve the validation assessment on deterministic result metadata

## Applying the patch

Patch the live worker container:

```bash
python scripts/apply_rxode2_patch.py --container pbpk_mcp-worker-1
```

Patch and restart a container:

```bash
python scripts/apply_rxode2_patch.py --container pbpk_mcp-worker-1 --restart
```

If an API container exists separately, patch that container too.

Recommended long-term path:

- use `scripts/apply_rxode2_patch.py` for development patching only
- use the prebuilt worker image from `docker/rxode2-worker.Dockerfile` for normal deployment

## Model path to use

After patching, the cisplatin model is copied to:

```text
/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R
```

## Example MCP calls

Load the model:

```json
{
  "tool": "load_simulation",
  "arguments": {
    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
    "simulationId": "cisplatin-rxode2"
  }
}
```

Example shape of the enriched load response:

```json
{
  "simulationId": "cisplatin-rxode2",
  "metadata": {
    "name": "Cisplatin population kidney model",
    "modelVersion": "2026-03-17-rxode2",
    "createdBy": "Codex",
    "backend": "rxode2"
  },
  "capabilities": {
    "populationSimulation": true,
    "validationHook": true,
    "scientificProfile": true,
    "supportedOutputs": [
      "Plasma|Cisplatin|Concentration"
    ],
    "applicabilityDomain": {
      "type": "declared-with-runtime-guardrails",
      "qualificationLevel": "research-use"
    }
  },
  "profile": {
    "contextOfUse": {
      "regulatoryUse": "research-only"
    },
    "uncertainty": {
      "status": "partially-characterized"
    },
    "implementationVerification": {
      "status": "basic-internal-checks"
    }
  },
  "validation": {
    "ok": true,
    "assessment": {
      "decision": "within-declared-guardrails",
      "qualificationLevel": "research-use",
      "oecdChecklistScore": 0.8
    }
  },
  "warnings": [
    "Applicability checks currently reflect runtime guardrails for this implementation, not external scientific qualification.",
    "Declared context of use is research-only; regulatory or cross-domain use requires additional qualification evidence."
  ]
}
```

The `validation.assessment` payload now also includes:

- `oecdChecklist`
  - structured per-dimension OECD-style metadata coverage
- `oecdChecklistScore`
  - a normalized completeness score derived from the checklist dimensions

Run a deterministic simulation:

```json
{
  "tool": "run_simulation",
  "arguments": {
    "simulationId": "cisplatin-rxode2",
    "runId": "cisplatin-demo"
  }
}
```

Run a population simulation:

```json
{
  "tool": "run_population_simulation",
  "arguments": {
    "modelPath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
    "simulationId": "cisplatin-rxode2",
    "cohort": {
      "size": 50,
      "seed": 42
    },
    "outputs": {
      "aggregates": ["meanCmax", "sdCmax", "meanAUC", "sdAUC"]
    }
  }
}
```

## Runtime prerequisite

The container still needs the R package `rxode2` installed. The patch script verifies syntax and reports whether `rxode2` is available, but it does not install R packages.

Preferred approach:

- build a dedicated `rxode2` worker image once
- keep runtime workers capped conservatively after the image is built
