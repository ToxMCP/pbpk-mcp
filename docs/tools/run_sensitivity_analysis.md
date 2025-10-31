# `run_sensitivity_analysis`

Executes a multi-parameter sensitivity sweep by orchestrating `load_simulation`,
`set_parameter_value`, `run_simulation`, `get_job_status`, and
`calculate_pk_parameters`. Returns a structured JSON report plus a CSV
attachment suitable for notebooks or BI tooling.

## Request schema

```json
{
  "modelPath": "reference/models/standard/midazolam_adult.pkml",
  "simulationId": "midazolam-sens",
  "parameters": [
    {
      "path": "Organism|Weight",
      "deltas": [-0.1, 0.1],
      "unit": "kg",
      "baselineValue": 72,
      "bounds": [60, 90]
    }
  ],
  "includeBaseline": true,
  "pollIntervalSeconds": 0.25,
  "jobTimeoutSeconds": 120
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `modelPath` | string | ✅ | Absolute path to the source `.pkml`. Must reside inside `MCP_MODEL_SEARCH_PATHS`. |
| `simulationId` | string | ✅ | Base simulation identifier. Derived scenarios append suffixes automatically. |
| `parameters` | array | ✅ | One entry per parameter; each entry requires `path` and at least one `delta`. |
| `parameters[].deltas` | array&lt;number&gt; | ✅ | Relative perturbations (e.g. `0.1` = +10%). |
| `parameters[].baselineValue` | number | ➖ | Optional fallback baseline when the adapter cannot read the parameter. |
| `includeBaseline` | boolean | ➖ | Add an unchanged baseline run to the report (default `true`). |
| `pollIntervalSeconds` | number | ➖ | Poll interval while waiting for jobs (default `0.25`). |
| `jobTimeoutSeconds` | number | ➖ | Optional deadline for the entire analysis. |

## Response structure

```json
{
  "report": {
    "simulation_id": "midazolam-sens",
    "model_path": "reference/models/standard/midazolam_adult.pkml",
    "baseline_metrics": [...],
    "scenarios": [...],
    "failures": []
  },
  "csv": {
    "filename": "midazolam-sens-20250101T120000Z.csv",
    "contentType": "text/csv",
    "data": "...base64...",
    "path": "/repo/reports/sensitivity/midazolam-sens-20250101T120000Z.csv"
  }
}
```

- `report` mirrors `SensitivityAnalysisReport` with baseline metrics and
  per-scenario deltas.
- `csv.data` encodes the same information in tabular form. Decode with
  `base64 --decode` to persist locally. The artefact is also stored on disk
  under `reports/sensitivity/`.
- `failures` contains textual descriptions of any scenarios that did not
  complete successfully (status and error message).

## Definition of Done

- ΔCmax/AUC for each scenario is computed relative to the baseline metric.
- Any missing metrics default to `null` and still appear in the CSV.
- Non-success job states populate `failures` and include the error message to
  aid debugging.

## Related tasks

- Baseline parity suite (`make parity`) provides pinned reference models.
- Quickstart walkthrough in
  `docs/mcp-bridge/getting-started/quickstart-cli.md#9-run-a-scripted-sensitivity-analysis`.
