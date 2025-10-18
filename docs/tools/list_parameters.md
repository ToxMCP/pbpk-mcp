# MCP Tool: `list_parameters`

Enumerates parameter paths for a previously loaded simulation, optionally
filtered by a search pattern.

## Request Schema

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `simulationId` | string | ✅ | Identifier returned by `load_simulation`. |
| `searchPattern` | string | ❌ | Wildcard expression understood by the adapter. Use `*` (default) to match all parameters. Newlines and null bytes are rejected. |

## Response Schema

```json
{
  "parameters": [
    "Organ.Liver.Weight",
    "Organ.Liver.Volume"
  ]
}
```

The array is sorted and deduplicated by the bridge prior to returning it to the
client. Large results are truncated to maintain predictable payload sizes.

## Error Handling

| HTTP Status | Error Code | Description |
| --- | --- | --- |
| 400 | `invalid-input` | Malformed simulation ID or search pattern. |
| 404 | `not-found` | The simulation ID is not registered in the session registry. |
| 5xx | Adapter-specific | Failures from the ospsuite adapter are propagated via the standard error shape. |

Each error includes an `X-Correlation-Id` header and is logged with structured
JSON (`simulation.parameters.invalid` for validation failures).

## Logging Signals

- `simulation.parameters.listed` – emitted on success with `simulationId`,
  `pattern`, and `count`.
- `simulation.parameters.invalid` – emitted when validation fails prior to
  adapter execution.

## Regression Coverage

- Unit tests validating the tool wrapper and registry interactions:
  `tests/unit/test_list_parameters_tool.py`.
- Integration tests covering the REST route, duplicate handling, and invalid patterns:
  `tests/integration/test_simulation_routes.py`.

These tests run inside the default `pytest` target and may be skipped in
environments where the R/ospsuite adapter is unavailable.
