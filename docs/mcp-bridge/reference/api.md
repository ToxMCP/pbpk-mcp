# HTTP API Reference

This page summarises the MCP Bridge REST surface. Detailed tool semantics live
in `docs/tools/`, while this document focuses on transport-level concerns,
required roles, and canonical request/response examples.

## OpenAPI specification

- Source file: `docs/mcp-bridge/contracts/openapi.json`
- Regenerate after changing routes:

```bash
PYTHONPATH=src python - <<'PY'
from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
import json, pathlib
app = create_app(AppConfig())
path = pathlib.Path("docs/mcp-bridge/contracts/openapi.json")
path.write_text(json.dumps(app.openapi(), indent=2))
PY
```

The generated schema targets OpenAPI 3.1 and can be rendered by tools such as
Redocly or Stoplight.

## Authentication

- All POST endpoints require a bearer token in `Authorization: Bearer <JWT>`.
- Role mapping is enforced via the `require_roles` dependency:
  - `viewer`: read-only operations (`list_parameters`, `get_*`, `calculate_pk_parameters`).
  - `operator`: mutation and job submission (`load_simulation`, `set_parameter_value`, `run_*`, `cancel_job`).
  - `admin`: superset of `operator`; needed for privileged automation flows.
- Development tokens can be minted with `AUTH_DEV_SECRET` (see quickstart guides).

## Endpoint catalogue

| Method | Path | Summary | Required roles |
| --- | --- | --- | --- |
| GET | `/health` | Service health/status information. | Public |
| POST | `/load_simulation` | Register a `.pkml` model under a simulation ID. | operator, admin |
| POST | `/list_parameters` | List parameters matching a search pattern. | viewer, operator, admin |
| POST | `/get_parameter_value` | Fetch current parameter value and metadata. | viewer, operator, admin |
| POST | `/set_parameter_value` | Update a parameter with unit normalisation. | operator, admin |
| POST | `/run_simulation` | Submit a single-subject simulation job. | operator, admin |
| POST | `/run_population_simulation` | Submit a population job with cohort/outputs config. | operator, admin |
| POST | `/get_job_status` | Poll job state, queue metrics, and result handles. | viewer, operator, admin |
| POST | `/get_simulation_results` | Retrieve time-series results for a simulation run. | viewer, operator, admin |
| POST | `/get_population_results` | Retrieve claim-check metadata and aggregates. | viewer, operator, admin |
| GET | `/population_results/{resultsId}/chunks/{chunkId}` | Stream a stored population chunk. | viewer, operator, admin |
| POST | `/calculate_pk_parameters` | Derive PK metrics from simulation results. | viewer, operator, admin |
| POST | `/cancel_job` | Request cancellation of a queued/running job. | operator, admin |

> Tool-specific payloads and validation rules remain documented under
> `docs/tools/`. Use the OpenAPI schema for precise field definitions.

## Sample flows

### Load → mutate → run

```bash
curl -s -X POST "$BASE_URL/load_simulation" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filePath":"tests/fixtures/demo.pkml","simulationId":"api-ref"}'

curl -s -X POST "$BASE_URL/set_parameter_value" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"simulationId":"api-ref","parameterPath":"Organism|Weight","value":70,"unit":"kg"}'

JOB_ID=$(curl -s -X POST "$BASE_URL/run_simulation" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"simulationId":"api-ref","runId":"api-ref-1"}' | jq -r '.jobId')
```

### Poll status and fetch results

```bash
STATUS=$(curl -s -X POST "$BASE_URL/get_job_status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\"}")
echo "$STATUS" | jq '.job | {status, queueWaitSeconds, runtimeSeconds}'

RESULTS_ID=$(echo "$STATUS" | jq -r '.job.resultHandle.resultsId')
curl -s -X POST "$BASE_URL/get_simulation_results" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resultsId\":\"$RESULTS_ID\"}" | jq '.series[0]'
```

### Population workloads

```bash
POP_JOB=$(curl -s -X POST "$BASE_URL/run_population_simulation" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "modelPath": "tests/fixtures/demo.pkml",
        "simulationId": "api-pop",
        "cohort": {"size": 200, "sampling": "latinHypercube", "seed": 42},
        "outputs": {"aggregates": ["mean", "p95"]}
      }' | jq -r '.jobId')

RESULT=$(curl -s -X POST "$BASE_URL/get_population_results" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resultsId\":\"$(curl -s -X POST \"$BASE_URL/get_job_status\" \
    -H \"Authorization: Bearer $TOKEN\" -H \"Content-Type: application/json\" \
    -d \"{\\\"jobId\\\":\\\"$POP_JOB\\\"}\" | jq -r '.job.resultHandle.resultsId')\"}")
echo "$RESULT" | jq '.aggregates'
```

To download bulk payloads, enumerate `chunks` within the population result and
issue a GET request against `/population_results/{resultsId}/chunks/{chunkId}`.

### PK metrics

```bash
curl -s -X POST "$BASE_URL/calculate_pk_parameters" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resultsId\":\"$RESULTS_ID\"}" | jq '.metrics[]'
```

The response mirrors `mcp.tools.calculate_pk_parameters` with optional CSV
export when `outputPath` is supplied.
