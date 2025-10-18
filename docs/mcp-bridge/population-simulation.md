# Population Simulation Requirements

## Goals

- Support ospsuite-based population simulations initiated through the MCP bridge.
- Allow the LangGraph agent and REST clients to configure cohorts, submit runs asynchronously, and retrieve aggregated outputs.
- Handle large result artefacts using a claim-check pattern and chunked streaming.
- Maintain backwards compatibility with existing single-subject simulation tools.

Need a guided example? See `getting-started/quickstart-cli.md` and the agent walkthrough in `getting-started/quickstart-agent.md`.

## Use Cases

1. **Regulatory validation** – run a cohort of 500 virtual subjects with varying renal function to quantify PK variability.
2. **Sensitivity + population** – execute sensitivity scenarios where each scenario is itself a population run, then compare summary statistics.
3. **Clinical trial simulation** – produce exposure predictions for multiple dosing regimens, storing raw time-series outputs for a subset of subjects and aggregate statistics for the full cohort.

## Inputs

- `modelPath` – absolute or registered path to the `.pkml` model file.
- `simulationId` – logical identifier for the population run (namespaced to avoid collisions with single-subject IDs).
- `cohort` – definition describing the virtual population:
  - `size`: number of individuals.
  - `sampling`: strategy (`fixed`, `random`, `latinHypercube`, etc.).
  - `covariates`: list of distributions or discrete sets (e.g. age, weight, renal clearance).
  - `seed`: optional deterministic seed for repeatability.
- `protocol` – dosing schedule overrides, if different from base model.
- `outputs` – requested endpoints:
  - time-series paths to persist per subject (optional subset).
  - aggregate statistics to compute (mean, SD, percentiles, Cmax, Tmax, AUC).
- `chunks` – optional chunk sizing directives when streaming results (e.g. `subjectBatch:50`, `timeSlice:1000`).
- `metadata` – free-form tags (study name, indication, analyst).

## Configuration Schema (JSON example)

```json
{
  "modelPath": "/data/models/finerenone.pkml",
  "simulationId": "finerenone-population-v1",
  "cohort": {
    "size": 500,
    "sampling": "latinHypercube",
    "seed": 12345,
    "covariates": [
      {
        "name": "Weight",
        "distribution": "lognormal",
        "mean": 75.0,
        "sd": 12.5
      },
      {
        "name": "RenalFunction",
        "levels": [
          {"label": "Normal", "probability": 0.6, "value": 1.0},
          {"label": "Mild", "probability": 0.25, "value": 0.75},
          {"label": "Moderate", "probability": 0.1, "value": 0.5},
          {"label": "Severe", "probability": 0.05, "value": 0.3}
        ]
      }
    ]
  },
  "protocol": {
    "dosingSchedule": [
      {"time": 0, "amount": 10, "unit": "mg"},
      {"time": 24, "amount": 10, "unit": "mg"}
    ]
  },
  "outputs": {
    "timeSeries": [
      {"path": "Plasma.Concentration", "subjects": 20},
      {"path": "Organ.Liver.Concentration", "subjects": 10}
    ],
    "aggregates": ["mean", "sd", "p5", "p50", "p95", "cmax", "tmax", "auc"]
  },
  "chunks": {
    "subjectBatch": 50,
    "timeSlice": 7200
  },
  "metadata": {
    "study": "Renal Impairment",
    "version": "draft"
  }
}
```

## Adapter Responsibilities

- **Initialization**: detect R/ospsuite capabilities for population runs, including any required R packages or scripts.
- **Submission**: accept the cohort/protocol configuration, prepare intermediate files, and invoke the ospsuite bridge with population parameters.
- **Progress reporting**: surface interim progress (subjects completed, percent complete) so the job service can publish status updates.
- **Result handling**:
  - Store raw outputs (typically large) using a claim-check interface: e.g. write to disk or object storage and return opaque handles.
  - Persist chunks under the configured `POPULATION_STORAGE_PATH` (default `var/population-results`) so the API can serve them without loading the entire payload into memory.
  - Produce aggregate summaries in-memory for minimal JSON payloads.
  - Support resumable/streaming reads for chunked downloads.
- **Cleanup**: remove temporary files after claim-check transfers are finalised.

### Configuration Notes

- `POPULATION_STORAGE_PATH` controls where chunk artefacts are written. The application resolves relative paths against the working directory and ensures the folder exists on startup.
- Storage paths should reside on fast local or network-attached volumes with sufficient quota for peak cohort output sizes.

## MCP Tool Requirements

1. `run_population_simulation`
   - Validates the configuration and enqueues an asynchronous population job via `JobService`.
   - Returns job metadata and an optional pre-signed URL token for when the first result chunk becomes available.

2. `get_population_results`
   - Accepts a `resultsId` and optional query parameters (metric list, subject subset, chunk cursor).
   - Returns either aggregate summaries or streaming chunk metadata.

3. `list_population_runs`
   - Provides a history of population jobs with status, configuration hashes, and claim-check locations.

## Claim-Check Pattern

- Population outputs can exceed JSON payload limits; use a two-step retrieval process:
  1. Job completion stores data (filesystem, S3, Azure Blob, etc.) under a stable key.
- The bridge exposes `GET /population_results/{resultsId}/chunks/{chunkId}` to stream chunk payloads (currently JSON) directly from storage, returning the `Content-Type` and size metadata declared in the handle.
- Chunk metadata now includes `uri`, `contentType`, `sizeBytes`, `subjectRange`, `timeRange`, and an inline preview for quick inspection.
- Aggregates remain inline to keep the API responsive.

## Performance Considerations

- Leverage `JobService` thread pool for submission, but allow configuration of worker count based on population size.
- Use lazy evaluation for chunk generation to avoid loading entire datasets into memory.
- Provide back-pressure friendly polling defaults (e.g. 500ms) with configurable overrides.
- Ensure configuration includes a hard timeout to prevent runaway jobs.

## Test Strategy

- Unit tests covering configuration validation and adapter submission stubs.
- Integration tests using mock adapters to simulate population bridge behaviour and chunked responses.
- Load tests (optional) to profile memory usage with large cohorts.
- Regression suite wired into `make test` once adapter/tool implementations land.
