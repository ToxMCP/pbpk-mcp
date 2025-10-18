# MCP Tool: `get_parameter_value`

Returns the current value (and unit) of a parameter identified by its full
path within an already loaded simulation.

## Request Schema

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `simulationId` | string | ✅ | Identifier returned from `load_simulation`. |
| `parameterPath` | string | ✅ | Fully-qualified path to the parameter (e.g. `Organ.Liver.Weight`). Newlines and null bytes are rejected. |

## Response Schema

```json
{
  "parameter": {
    "path": "Organ.Liver.Weight",
    "value": 2.0,
    "unit": "kg",
    "displayName": "Liver Weight",
    "lastUpdatedAt": "2025-10-14T23:00:00Z"
  }
}
```

All fields except `path`, `value`, and `unit` are optional and reflect adapter
metadata when available.

## Error Handling

| HTTP Status | Error Code | Description |
| --- | --- | --- |
| 400 | `invalid-input` | Malformed simulation ID or parameter path. |
| 404 | `not-found` | Simulation ID not loaded or parameter missing. |
| 5xx | Adapter-specific | Errors from the underlying ospsuite adapter are mapped through the common error template. |

Responses include the correlation ID header `X-Correlation-Id`, and the server
emits structured logs:

- `simulation.parameter.read` (success)
- `simulation.parameter.invalid` (validation failure)
- `simulation.parameter.error` (not found / adapter error)

## Regression Coverage

- Unit tests: `tests/unit/test_get_parameter_value_tool.py`
- Integration flow: `tests/integration/test_simulation_routes.py`

Both run as part of the default `pytest` target, with adapter-dependent tests
skipping gracefully when the R runtime is unavailable.
