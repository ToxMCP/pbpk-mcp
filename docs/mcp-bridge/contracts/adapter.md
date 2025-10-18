# ospsuite Adapter Interface (Draft)

Companion to Task 3.1 providing the initial adapter API surface implemented in Python.

## Public Types

Module: `mcp_bridge.adapter`

- `AdapterConfig`: dataclass capturing runtime settings such as `ospsuite_libs` path and default timeouts.
- `AdapterConfig.model_search_paths`: optional tuple of directories used to validate simulation
  files before they are passed to the bridge.  Defaults to the working directory or values from
  `MCP_MODEL_SEARCH_PATHS`.
- `OspsuiteAdapter`: abstract base class defining required operations for session lifecycle, parameter management, and synchronous simulation execution.
- `AdapterError` / `AdapterErrorCode`: exception hierarchy aligning with service error taxonomy (`InvalidInput`, `NotFound`, `EnvironmentMissing`, `InteropError`, `Timeout`).
- `SimulationHandle`, `ParameterSummary`, `ParameterValue`, `SimulationResult`, `SimulationResultSeries`: pydantic models ensuring JSON-safe payloads.

## Responsibilities

| Method | Description | Returns |
| --- | --- | --- |
| `init()` | Start or verify the backing R/ospsuite runtime. | `None` |
| `shutdown()` | Dispose resources, flush temp data, shut down runtime. | `None` |
| `health()` | Diagnostics e.g., ospsuite version, status. | `dict[str, str]` |
| `load_simulation(file_path, simulation_id?)` | Load `.pkml` from allow-listed paths. | `SimulationHandle` |
| `list_parameters(simulation_id, pattern?)` | Enumerate parameters matching wildcard. | `list[ParameterSummary]` |
| `get_parameter_value(simulation_id, parameter_path)` | Fetch a parameter with unit metadata. | `ParameterValue` |
| `set_parameter_value(simulation_id, parameter_path, value, unit, comment?)` | Apply validated mutation. | `ParameterValue` |
| `run_simulation_sync(simulation_id, run_id?)` | Execute synchronously for immediate feedback; async orchestration handled elsewhere. | `SimulationResult` |
| `get_results(results_id)` | Retrieve stored results by handle. | `SimulationResult` |

## Reference Implementation

- `SubprocessOspsuiteAdapter` (`src/mcp_bridge/adapter/ospsuite.py`) shells out to an external
  bridge (intended to be an R script) using a pluggable command runner.  It validates model
  paths against an allow-list (`AdapterConfig.model_search_paths`), hydrates pydantic models
  from JSON responses, caches parameter metadata, and maps bridge failures into
  `AdapterError` instances.
- `InMemoryAdapter` (`src/mcp_bridge/adapter/mock.py`) mocks the interface for test scaffolding,
  handling in-memory storage of simulations/parameters/results, `.pkml` extension checks,
  error raising with `AdapterErrorCode`, and a deterministic sample result series for integration
  smoke tests. When a population store is provided it persists chunk payloads to disk and returns
  claim-check metadata (`uri`, `contentType`, `sizeBytes`) for retrieval via the API.

Unit tests (`tests/unit/test_adapter_interface.py`) cover lifecycle, parameter CRUD, error propagation, and result retrieval.

## FastAPI Integration

The application factory wires the adapter into FastAPI and surfaces REST routes in
`src/mcp_bridge/routes/simulation.py`:

- `/load_simulation`
- `/list_parameters`
- `/get_parameter_value`
- `/set_parameter_value`
- `/run_simulation`
- `/get_job_status`
- `/get_simulation_results`
- `/get_population_results`
- `/population_results/{resultsId}/chunks/{chunkId}` (stream population chunks via claim-check)

`JobService` (`src/mcp_bridge/services/job_service.py`) provides an in-memory job registry so
the synchronous `run_simulation_sync` results can be exposed via asynchronous-style job status
and result retrieval flows. Integration tests (`tests/integration/test_simulation_routes.py`) cover
the end-to-end pipeline.

Environment detection is handled in `src/mcp_bridge/adapter/environment.py`. When
`AdapterConfig.require_r_environment` is enabled the adapter raises `EnvironmentMissing`
errors if the R binary or ospsuite libraries cannot be located. The health endpoint reports the
detected R version, library path, and outstanding issues to aid operators.

## Environment Variables

The adapter is configured via environment variables surfaced through `AppConfig`:

- `ADAPTER_BACKEND` – selects `inmemory` or `subprocess` backend (default `inmemory`).
- `ADAPTER_REQUIRE_R_ENV` – set to `true` to fail startup when R/ospsuite are missing.
- `ADAPTER_TIMEOUT_MS` – default timeout (milliseconds) for bridge operations.
- `ADAPTER_R_PATH`, `ADAPTER_R_HOME`, `ADAPTER_R_LIBS` – override R binary/home/library lookup.
- `OSPSUITE_LIBS` – absolute path to the ospsuite R packages when using the subprocess backend.
- `ADAPTER_MODEL_PATHS` – colon-separated allow list of `.pkml` directories.
- `MCP_RUN_R_TESTS` – set to `1` to run subprocess integration tests in CI/local workflows.
- `JOB_WORKER_THREADS` – size of the in-process worker pool for asynchronous jobs.
- `JOB_TIMEOUT_SECONDS` – execution timeout applied to each job run.
- `JOB_MAX_RETRIES` – automatic retry attempts for transient job failures.
- `POPULATION_STORAGE_PATH` – directory where population chunk artefacts are written (default `var/population-results`).
