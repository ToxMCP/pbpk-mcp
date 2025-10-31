# `cancel_job`

Request termination of a queued or running simulation job. The bridge marks the
job record as `cancel_requested` and attempts to halt execution. Clients should
continue polling `get_job_status` until the job reaches a terminal state.

## Request

```json
{
  "jobId": "8e7d5b9a-5c7f-4c3f-9a2f-1a2b3c4d5e6f"
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `jobId` | `string` | ✅ | Identifier returned by `run_simulation` or `run_population_simulation`. |

## Response

```json
{
  "jobId": "8e7d5b9a-5c7f-4c3f-9a2f-1a2b3c4d5e6f",
  "status": "cancelled"
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `jobId` | `string` | Echo of the requested job. |
| `status` | `string` | Current status after the cancellation attempt. Values mirror `get_job_status` (`queued`, `running`, `cancelled`, etc.). |

The response reports the state immediately after the request. Jobs that are
already running may surface `running` until the worker drains in-flight work and
acknowledges the cancellation flag. Poll `get_job_status` to observe the final
transition to `cancelled`, `succeeded`, or `failed`.

## Behaviour

- Jobs marked `cancel_requested` are removed from the queue before execution.
- Running jobs cooperate with cancellation points inside the worker loop; if the
  adapter call has already returned, the job may still reach `succeeded`.
- Cancelled jobs retain submission metadata for auditability but omit result
  handles.
- The tool requires `operator` or `admin` role assignments.

## Error codes

| HTTP status | Error code | Meaning | Recommended handling |
| --- | --- | --- | --- |
| `404` | `NOT_FOUND` | No job record matches the supplied ID, or the job has already completed. | Stop polling and surface the error to the user. |

All other errors follow the shared error taxonomy (rate limits, auth failures,
and transport issues).

## CLI example

```bash
curl -s -X POST "$BASE_URL/cancel_job" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\"}" | jq
```

Follow up with `get_job_status` until the job reaches a terminal state:

```bash
curl -s -X POST "$BASE_URL/get_job_status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"jobId\":\"$JOB_ID\"}" | jq '.job.status'
```
