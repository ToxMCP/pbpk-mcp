# MCP Bridge Error Taxonomy

The bridge surfaces a stable set of error codes that align with the OpenAPI specification (`openapi.json`) and centralized error handling in the FastAPI service. Every error payload follows the structure:

```json
{
  "error": {
    "code": "<ErrorCode>",
    "message": "<human readable context>",
    "correlationId": "<request correlation id>",
    "retryable": false,
    "details": [
      {
        "field": "parameterPath",
        "issue": "expected format Simulation.Parameter.Path",
        "severity": "error"
      }
    ]
  }
}
```

## Error Codes

| Error Code | HTTP Status | Description | Retry Guidance | Typical Sources |
| --- | --- | --- | --- | --- |
| `InvalidInput` | 400 | Payload failed validation or violates guard rails (e.g., unsafe file path, malformed parameter). | Caller must fix request before retrying. | JSON schema validation, adapter argument checks. |
| `NotFound` | 404 | Requested resource does not exist (simulation handle, parameter path, job id). | Retrying after creating/loading the resource may succeed. | Registry lookup failures, expired handles. |
| `Conflict` | 409 | Operation conflicts with current state (e.g., duplicate simulation id, concurrent update). | Retry after resolving conflict (different id, retry once job completes). | Attempts to reuse identifiers, optimistic concurrency checks. |
| `EnvironmentMissing` | 503 | Required runtime dependency (R, ospsuite) unavailable or unhealthy. | Retry after environment remediation; treated as transient. | R session bootstrap, ospsuite version mismatch. |
| `InteropError` | 502 | Underlying R/ospsuite call failed unexpectedly. | Often transient; retry if root cause addressed. | ospsuite exceptions, serialization failures. |
| `Timeout` | 504 | Operation exceeded allowed execution time (e.g., R call timeout, job exceeded SLA). | Retry only if load conditions change; monitor queue saturation. | Long-running simulations, stalled I/O to storage. |
| `InternalError` | 500 | Unexpected server failure outside known categories. | Retry cautiously; investigate logs using `correlationId`. | Bug in bridge code, uncaught adapter exception. |

## Correlation ID Propagation

- All error responses include the `X-Correlation-Id` response header and the same value in `error.correlationId`.
- If the caller provides `X-Correlation-Id`, the bridge echoes it; otherwise, a UUID v4 is generated.
- Operators use the correlation id to trace logs across the bridge, job worker, and adapter layers.

## Details Array

- Optional `error.details` entries provide field-level validation issues or contextual hints.
- Each detail entry contains:
  - `field`: the logical field or domain component.
  - `issue`: brief description of the problem.
  - `severity`: one of `info`, `warning`, or `error` (default).

## Logging Expectations

- Every error response emits a structured log event (`http.error` or `http.unhandled_error`) with the correlation id, HTTP status, and redacted message.
- Sensitive fragments (tokens, secrets, passwords, keys) are redacted automatically before logging or returning in the response.
