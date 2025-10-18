# MCP Tool: `load_simulation`

Loads a PBPK `.pkml` model into the MCP Bridge session registry, returning a
`simulation_id` that subsequent tools can use when querying or updating model
state.

## Request Schema

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `filePath` | string | ✅ | Absolute or workspace-relative path to a `.pkml` file. The path must resolve inside the directories specified by `MCP_MODEL_SEARCH_PATHS` (or the default fixture directory during development). |
| `simulationId` | string | ❌ | Custom identifier to register the model under. When omitted, the file stem is used. IDs are trimmed and limited to 64 characters.

## Response Schema

```json
{
  "simulationId": "sim-001",
  "metadata": {
    "name": "My PBPK Model",
    "modelVersion": "1.0.0"
  },
  "warnings": []
}
```

The `metadata` block mirrors information returned by the ospsuite adapter. Fields
are optional; tools should treat missing keys as unknown values.

## Error Handling

| HTTP Status | Error Code | Description |
| --- | --- | --- |
| 400 | `invalid-input` | File path outside the allowlist, missing file, bad extension, or malformed identifier. |
| 409 | `conflict` | A simulation with the same identifier is already registered. |
| 5xx | Adapter-specific | Errors raised by the ospsuite adapter are translated through the global error handler (e.g., `EnvironmentMissing` → 503). |

Errors include the standard MCP Bridge correlation ID via the
`X-Correlation-Id` header and are logged with structured JSON (`simulation.invalid`
for validation failures, `simulation.duplicate` for conflicts).

## Logging Signals

- `simulation.loaded` – emitted on success with `simulationId` and `filePath`.
- `simulation.invalid` – emitted on validation failure prior to invoking the adapter.
- `simulation.duplicate` – emitted when a conflicting `simulationId` is detected.

All messages inherit the request correlation ID from the middleware so that REST
and MCP interactions can be correlated in downstream observability tools.

## Regression Coverage

The automated test suite includes:

- Unit tests for path validation, duplicate detection, and session registry
  interactions (`tests/unit/test_load_simulation_validation.py`,
  `tests/unit/test_load_simulation_tool.py`).
- Integration tests that load a demo PKML, assert duplicate protection, and
  verify invalid extensions raise a 400 (`tests/integration/test_simulation_routes.py`).

These tests run under the standard `pytest` target, ensuring the contract stays
stable as the adapter implementation evolves.
