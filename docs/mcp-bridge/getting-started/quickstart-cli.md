# Quickstart: MCP Bridge via REST & CLI

This tutorial walks through the end-to-end workflow for operating the MCP Bridge
with simple command-line tools. You will:

1. Install dependencies and start the FastAPI server.
2. Mint a development JWT for local authentication.
3. Load a PBPK model, inspect parameters, and apply an update.
4. Submit an asynchronous simulation and fetch its results.
5. Calculate PK metrics, launch a population run, and trigger a small sensitivity study.

The commands assume macOS/Linux shells; adapt for PowerShell when needed.

## Prerequisites

- Python 3.9+ (matches the version used in CI) with `pip`.
- Optional: R 4.2+ with the `ospsuite` package if you want to exercise the subprocess adapter.
- CLI utilities:
  - `curl` or `httpie` for REST calls.
  - `jq` for JSON parsing (optional but convenient).

All examples use repository paths relative to the project root.

## 1. Install and bootstrap

```bash
make install
```

The command installs the package in editable mode with development extras, matching the CI setup.

## 2. Start the MCP Bridge server

Open a dedicated terminal and start the FastAPI app with an in-memory adapter and a development JWT secret:

```bash
export AUTH_DEV_SECRET=dev-secret
export ADAPTER_BACKEND=inmemory
export MCP_MODEL_SEARCH_PATHS=$(pwd)/tests/fixtures
PYTHONPATH=src uvicorn mcp_bridge.main:app --host 127.0.0.1 --port 8000 --reload
```

The server listens on `http://127.0.0.1:8000` and allows `.pkml` files inside `tests/fixtures/`.

## 3. Mint a development JWT

In a new terminal, generate a short-lived token using the same secret:

```bash
export AUTH_DEV_SECRET=dev-secret
export MCP_TOKEN=$(PYTHONPATH=src python -c "from mcp_bridge.security.simple_jwt import jwt; print(jwt.encode({'sub': 'cli-quickstart', 'roles': ['admin']}, '$AUTH_DEV_SECRET', algorithm='HS256'))")
```

Confirm the token is set:

```bash
echo $MCP_TOKEN
```

All subsequent `curl` commands include:

```bash
AUTH_HEADER="Authorization: Bearer $MCP_TOKEN"
BASE_URL="http://127.0.0.1:8000"
```

## 4. Load a PBPK model

```bash
curl -s -X POST "$BASE_URL/load_simulation" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "filePath": "tests/fixtures/demo.pkml",
        "simulationId": "cli-demo"
      }' | jq
```

Expected response (abbreviated):

```json
{
  "simulationId": "cli-demo",
  "metadata": {
    "name": "Demo Simulation",
    "modelVersion": "1.0.0"
  },
  "warnings": []
}
```

## 5. Inspect and edit a parameter

List matching parameters:

```bash
curl -s -X POST "$BASE_URL/list_parameters" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "simulationId": "cli-demo",
        "searchPattern": "Organism|*|Weight"
      }' | jq '.parameters[0]'
```

Update the weight to `72 kg`:

```bash
curl -s -X POST "$BASE_URL/set_parameter_value" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "simulationId": "cli-demo",
        "parameterPath": "Organism|Weight",
        "value": 72.0,
        "unit": "kg",
        "comment": "CLI quickstart adjustment"
      }' | jq '.parameter'
```

Verify the change:

```bash
curl -s -X POST "$BASE_URL/get_parameter_value" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "simulationId": "cli-demo",
        "parameterPath": "Organism|Weight"
      }' | jq '.parameter.value'
```

## 6. Submit and monitor a simulation

Submit the job:

```bash
RUN_RESPONSE=$(curl -s -X POST "$BASE_URL/run_simulation" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "simulationId": "cli-demo",
        "runId": "cli-demo-run-1"
      }')
JOB_ID=$(echo "$RUN_RESPONSE" | jq -r '.jobId')
echo "Job ID: $JOB_ID"
```

Poll until completion:

```bash
while true; do
  STATUS=$(curl -s -X POST "$BASE_URL/get_job_status" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "{\"jobId\": \"$JOB_ID\"}")
  STATE=$(echo "$STATUS" | jq -r '.job.status')
  echo "Status: $STATE"
  if [[ "$STATE" != "queued" && "$STATE" != "running" ]]; then
    RESULTS_ID=$(echo "$STATUS" | jq -r '.job.resultId // empty')
    break
  fi
  sleep 1
done
echo "Results ID: $RESULTS_ID"
```

Retrieve time-series output (if available):

```bash
curl -s -X POST "$BASE_URL/get_simulation_results" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "{\"resultsId\": \"$RESULTS_ID\"}" | jq '.results.summary'
```

## 7. Calculate PK parameters

```bash
curl -s -X POST "$BASE_URL/calculate_pk_parameters" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "{\"resultsId\": \"$RESULTS_ID\"}" | jq '.metrics[] | {parameter, cmax, tmax, auc}'
```

Override the output path to persist CSV summaries by adding `"outputPath": "var/benchmarks/pk-cli-demo.csv"` to the request payload.

## 8. Launch a population run

```bash
POP_RESPONSE=$(curl -s -X POST "$BASE_URL/run_population_simulation" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
        "modelPath": "tests/fixtures/demo.pkml",
        "simulationId": "cli-pop-1",
        "cohort": {"size": 100, "sampling": "latinHypercube", "seed": 101},
        "outputs": {"aggregates": ["mean", "p5", "p95"]},
        "metadata": {"study": "Quickstart"}
      }')
POP_JOB=$(echo "$POP_RESPONSE" | jq -r '.jobId')
echo "Population job: $POP_JOB"
```

Poll the job as above. When it succeeds, use:

```bash
curl -s -X POST "$BASE_URL/get_population_results" \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d "{\"resultsId\": \"$(echo "$STATUS" | jq -r '.job.resultId')\"}" | jq '.aggregates'
```

Chunk metadata includes claim-check URIs for large payloads when the subprocess adapter is enabled.

## 9. Run a scripted sensitivity analysis

Create `scripts/sensitivity_quickstart.py` with:

```python
import pathlib

from mcp import session_registry
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.adapter.interface import AdapterConfig
from mcp_bridge.agent.sensitivity import (
    SensitivityConfig,
    SensitivityParameterSpec,
    run_sensitivity_analysis,
)
from mcp_bridge.services.job_service import JobService

fixture = pathlib.Path("tests/fixtures/demo.pkml")
adapter = InMemoryAdapter(AdapterConfig(model_search_paths=[str(fixture.parent)]))
adapter.init()

job_service = JobService(max_workers=2, default_timeout=60.0, max_retries=0)

config = SensitivityConfig(
    model_path=fixture,
    base_simulation_id="cli-sens",
    parameters=[SensitivityParameterSpec(path="Organism|Weight", deltas=[-0.1, 0.1])],
)

report = run_sensitivity_analysis(adapter, job_service, config)
print(report.model_dump_json(indent=2))

job_service.shutdown()
adapter.shutdown()
session_registry.clear()
```

Run it with:

```bash
PYTHONPATH=src python scripts/sensitivity_quickstart.py
```

The JSON report summarises baseline metrics, scenario deltas, and any failures.

## 10. Where to go next

- Explore interactive agent automation in [Quickstart: LangGraph Agent](quickstart-agent.md).
- Dive deeper into scientific workflows via [`workflows/sensitivity-analysis.md`](../sensitivity-analysis.md) and [`workflows/population-simulation.md`](../population-simulation.md).
- Review configuration and auth details in [`../authentication.md`](../authentication.md).

Capture screenshots or plots from your runs and store them under `docs/assets/` for use in future tutorials.
- For detailed endpoint descriptions, consult the API reference in `../reference/api.md`.
