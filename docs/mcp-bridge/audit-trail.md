# Immutable Audit Trail Design

## 1. Goals

- Capture every MCP tool invocation with tamper-evident records spanning request metadata, identity context, and outcomes.
- Provide append-only retention with cryptographic hash chaining for forensic verification.
- Support replay/verification tooling and integration with downstream compliance stores (e.g., WORM buckets, object lock).
- Surface audit correlation IDs in logs, LangGraph agents, and future reporting UIs.

## 2. Event Scope

| Source | Trigger |
| --- | --- |
| FastAPI routes | Entry/exit of each MCP HTTP endpoint (`load_simulation`, `set_parameter_value`, etc.). |
| Job Service | State transitions for asynchronous jobs (`queued`, `running`, `succeeded`, `failed`, `cancelled`). |
| LangGraph agent | High-level agent actions (planner decisions, human confirmations) to provide contextual breadcrumbs. |

Each event is recorded even if the underlying action fails, ensuring visibility of attempted operations.

## 3. Event Schema

JSON object written per event:

```json
{
  "eventId": "uuid",
  "timestamp": "2025-10-16T13:42:12.123Z",
  "eventType": "http.mcp.set_parameter_value",
  "correlationId": "req-uuid",
  "identity": {
    "subject": "operator-user",
    "roles": ["operator"],
    "isServiceAccount": false,
    "tokenId": "..."
  },
  "request": {
    "method": "POST",
    "path": "/set_parameter_value",
    "bodyDigest": "sha256:...",
    "parameters": {
      "parameterPath": "Organism|Weight",
      "simulationId": "renal-study"
    }
  },
  "response": {
    "status": 200,
    "bodyDigest": "sha256:...",
    "durationMs": 125.3
  },
  "job": {
    "jobId": "job-uuid",
    "status": "succeeded"
  },
  "hash": "sha256:...",
  "previousHash": "sha256:..."
}
```

Key points:
- **bodyDigest** captures a salted SHA-256 hash of request/response payloads (raw bodies stored separately if required).
- **identity** comes directly from `AuthContext` (Task 17), enabling analyst attribution.
- **eventType** namespace (`http.mcp.*`, `job.*`, `agent.*`) allows filtering.
- **hash/previousHash** implement a linear chain per log stream.

## 4. Hash Chaining Strategy

- Maintain a rolling hash per append-only log file/partition.
- For each new event `E_n`, compute `hash_n = SHA256(eventPayload || previousHash_n-1)`.
- Store `previousHash` field in the event and persist `hash_n` as the new tail.
- Periodically (e.g., hourly) emit checkpoints summarising the current tail hash to an external registry (e.g., S3 object metadata, DynamoDB, or anchored to a blockchain) for tamper detection.

## 5. Storage & Retention

| Environment | Storage | Notes |
| --- | --- | --- |
| Development | Local append-only JSONL files under `var/audit/` | Simplifies testing; still hash-chained. |
| Production | S3 bucket with Object Lock/WORM (Governance or Compliance mode). | Events written as immutable objects (`prefix/YYYY/MM/DD/<timestamp>-<eventId>.jsonl`) with per-object retention. |
| Long-term archive | Glacier / Offline storage | Retention policies derived from regulatory guidance (e.g., 7-10 years). |

Retention strategy:
- Primary store retains 18 months online for fast querying.
- Archived copies hashed and stored offline; verification tool replays chain before archiving.
- Deletion allowed only via documented process with multi-party approval; otherwise records are immutable.

## 6. Ingestion Pipeline

1. **Middleware hook** – FastAPI middleware captures request metadata and enqueues audit events before/after route execution.
2. **Job service integration** – `JobService` emits audit events on status transitions (submit, start, success, failure, timeout, cancel).
3. **Background writer** – dedicated asyncio task flushes events to storage, updating hash chain; backpressure-resistant queue ensures audit logging does not block hot path.
4. **Failure handling** – on writer failure, application transitions to degraded mode:
   - emit structured error logs,
   - optionally reject mutating requests (`503`) until audit persistence recovers (configurable).

## 7. Verification Tools

- `audit verify --from 2025-10-16` – Streams events, recomputes hash chain, validates against stored tail hash.
- `audit replay --job job-uuid` – Reconstructs timeline for a specific job or correlation ID.
- `audit export --range 2025-10-16..2025-10-17 --format parquet` – Curated extracts for compliance teams.

### CLI Helper

During development you can run:

```bash
python -m mcp_bridge.audit.verify var/audit
```

This replays events in the local audit directory and exits non-zero if tampering is detected. Supply `--start` and `--end` date keys (`YYYY/MM/DD`) to limit verification windows.

For S3 deployments:

```bash
python -m mcp_bridge.audit.verify s3://my-audit-bucket/bridge/audit \
  --object-lock-mode governance \
  --object-lock-days 90
```

The verifier recomputes hash chains across all objects under the prefix and confirms Object Lock
mode/retention match policy expectations.

## 8. API access

- `GET /audit/events?limit=100&eventType=tool.run_simulation` returns the most recent audit events (requires `admin` role).
- Events recorded via `/mcp/call_tool` include:
  - `identity` (subject, roles, token metadata)
  - tool name, argument digest, and a summary of key fields
  - execution status, duration, service version, and optional idempotency key
  - result digest + summary to support tamper detection without leaking payload contents.

For larger exports, prefer the CLI verification tools to stream directly from storage.

Scheduled automation can reuse the helper at `python -m mcp_bridge.audit.jobs`, which loads
`AppConfig` and verifies the last `AUDIT_VERIFY_LOOKBACK_DAYS` of events against the configured
backend. This command is designed to run in CI or a cron-driven maintenance container.

## 8. Integration Points

- **Logging** – existing structured logs reference `correlationId`; audit events reuse this field for cross-linking.
- **AuthContext** – identity metadata added to every audit event, fulfilling threat model requirements.
- **LangGraph agent** – planner/executor nodes emit `agent.*` events when entering confirmation gates, capturing human approvals.

## 9. Open Questions / Next Steps

- Decide on managed event pipelines (e.g., Kafka) vs. direct object storage for high-traffic deployments.
- Evaluate compression/encryption strategies compliant with data-governance requirements.
- Define SOP for anchoring tail hashes to external ledgers (optional, but strengthens tamper evidence).
- Estimate storage footprint and incorporate into Performance & Scalability plan (Task 19).

## 10. Testing & Operational Playbook

- **Automated tests** – `pytest tests/unit/test_audit_trail.py tests/unit/test_audit_verify.py` validates hash chaining and tamper detection (a corrupted record triggers failure).
- **CI hook** – Add a pipeline job that runs `python -m mcp_bridge.audit.verify var/audit` after integration tests to ensure the generated logs remain consistent.
- **Manual verification** – Before releasing or archiving logs, operators run the CLI helper across the storage bucket. Any non-zero exit code indicates corruption and should halt deployment.
- **SOP for incidents** – On hash mismatch:
  1. Quarantine the affected log partition and capture copies for forensic analysis.
  2. Re-run verification to determine earliest failing record.
  3. Escalate to compliance/infosec; avoid pruning until investigation is complete.
  4. Restore from immutable backup if tampering is confirmed.

This design satisfies Task 18.1 and feeds into future implementation subtasks covering middleware, immutable storage, verification jobs, and documentation.
