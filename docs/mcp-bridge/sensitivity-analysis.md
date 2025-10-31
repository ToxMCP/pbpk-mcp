# Sensitivity Analysis Workflow

## Goals

- Automate one-factor-at-a-time sensitivity studies driven by the MCP toolset.
- Support repeatable configuration: parameter selection, perturbation magnitudes, batching.
- Leverage existing asynchronous job service and PK metric tooling to produce summary tables.
- Provide an extensible core that the LangGraph agent can call as a single step.

For a hands-on walkthrough, start with `getting-started/quickstart-cli.md` and
the executable notebook at `../notebooks/sensitivity_analysis_walkthrough.ipynb`.

## Inputs

- `simulation_id`: identifier of a simulation already loaded via `load_simulation`.
- `parameters`: list of parameter specs:
  - `path`: MCP parameter path (e.g. `Organism|Weight`).
  - `deltas`: list of percentage adjustments (e.g. `[-0.25, 0.25, 0.5]`).
  - `unit`: optional override for `set_parameter_value` (defaults to adapter metadata).
  - `bounds`: optional `(min, max)` absolute value primitives.
- `baseline`: flag controlling whether the workflow runs an unchanged baseline simulation.
- `metrics`: optional list of PK outputs to surface (defaults to all returned by `calculate_pk_parameters`).
- `poll_interval`: seconds between job status checks.
- `timeout_seconds`: per-job timeout ceiling.

## Steps

1. **Baseline snapshot**
   - Query `get_parameter_value` for each sensitivity parameter and cache baseline values.
   - Optionally schedule a baseline run (`run_simulation`).

2. **Variation generation**
   - For each parameter, compute absolute target values using `baseline_value * (1 + delta)`.
   - Enforce optional bounds.
   - Build `SensitivityScenario` objects containing:
     - parameter metadata
     - delta metadata (percent change, absolute value)
     - unique identifier for linking results (`scenario_id`)

3. **Async submission**
   - For each scenario:
     - `set_parameter_value` to target value.
     - call `run_simulation` (store job_id ⇔ scenario mapping).
   - After all variations dispatched, restore original baseline values via `set_parameter_value`.

4. **Job management**
   - Poll `get_job_status` until all jobs reach a terminal state or exceed timeout.
   - Collect `resultsId` for succeeded jobs.

5. **PK metric aggregation**
   - For each successful scenario, call `calculate_pk_parameters` (optionally filtered by `metrics`).
   - Persist metrics alongside scenario metadata.
   - Derive deltas relative to the baseline metrics: `% change = (scenario - baseline) / baseline * 100`.

6. **Reporting**
   - Produce a `SensitivityAnalysisReport` containing:
     - Run metadata (simulation id, configuration hash, timestamp)
     - Baseline metrics
     - Scenario table with columns: parameter path, delta %, absolute value, job status, metric deltas.
     - Optional CSV/JSON serialisation helpers.

## MCP tool interface

The bridge exposes the workflow as the `run_sensitivity_analysis` MCP tool. The
request maps directly to the configuration fields above and accepts JSON like:

```json
{
  "modelPath": "reference/models/standard/midazolam_adult.pkml",
  "simulationId": "midazolam-sens",
  "parameters": [
    {
      "path": "Organism|Weight",
      "deltas": [-0.1, 0.1],
      "baselineValue": 72,
      "unit": "kg"
    }
  ],
  "includeBaseline": true,
  "pollIntervalSeconds": 0.25,
  "jobTimeoutSeconds": 120
}
```

Responses contain two structured elements:

- `report`: JSON serialisation of `SensitivityAnalysisReport` (baseline metrics,
  per-scenario deltas, failures).
- `csv`: attachment metadata with `filename`, `contentType`, `path`, and a
  Base64-encoded CSV payload.

CSV artefacts are also persisted under `reports/sensitivity/<simulation>-<timestamp>.csv`
so downstream automation and CI jobs can archive them without re-running the
analysis.

## Error Handling

- Any failed job is reported with status `failed` and associated error message; metric deltas default to `None`.
- The workflow surfaces a summary list of failures for quick inspection.
- Timeouts raise `SensitivityAnalysisError` including job ids still pending.

## Extensibility

- The generator can be extended to support multi-parameter perturbations by allowing `parameters` entries with `coupled=True` and providing a list of parameter/value pairs per scenario.
- Integrates cleanly with LangGraph by exposing a single callable returning a structured report the agent can summarise.
