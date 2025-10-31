# MCP Bridge Service Runbook

> **Version:** 2025-10-30 – Maintainer rotation: Platform Engineering (platform@mcp.local)

This runbook documents the day-to-day operations of the MCP bridge that exposes
PK‑Sim®/MoBi® tooling via MCP. It acts as the single source of truth for
startup, health verification, incident response, and rollback drills.

---

## 1. System Overview

| Component | Purpose | Notes |
| --- | --- | --- |
| FastAPI app (`uvicorn mcp_bridge.app:create_app`) | Serves REST + MCP routes, hosts analyst console. | Runs with structured JSON logs and Prometheus middleware. |
| Job service (thread / Celery / HPC stub) | Executes simulations asynchronously. | Backed by `DurableJobRegistry` (SQLite). HPC stub assigns `SLURM-*` external IDs. |
| Adapter (`inmemory` / `subprocess`) | Bridges to ospsuite R. | `subprocess` backend requires R + ospsuite libs; `inmemory` used for CI. |
| Storage | `var/` hierarchy (jobs, snapshots, population results, audit). | Snapshots in `var/snapshots`; audit trail hashed and append-only. |
| Observability | `/metrics`, structured logs, audit events. | Prom histogram names `mcp_http_*`; audit events chained via SHA-256. |

Upstream dependencies include Redis (optional for session registry), Celery
broker/result backend (for distributed mode), and object storage if the audit
trail is configured for S3.

---

## 2. Startup Procedures

### 2.1 Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export ADAPTER_BACKEND=inmemory
uvicorn mcp_bridge.app:create_app --factory --reload
```

Optional knobs:

- `JOB_BACKEND=celery` with `make celery-worker` in another shell.
- `JOB_BACKEND=hpc` to exercise the stub scheduler (see `docs/operations/hpc.md`).
- `SNAPSHOT_STORAGE_PATH` to relocate baseline snapshots from `var/snapshots`.

### 2.2 Container / compose

```bash
docker compose -f docker-compose.celery.yml up --build
```

Ensures API, worker, and Redis start with shared `var/` volume.

### 2.3 Production deployment checklist

1. Confirm artefacts built from `main` with green CI (run `make check`).
2. Publish container image with release tag.
3. Apply Terraform/Helm updates (if applicable) and run smoke (`make benchmark`).
4. Verify `/health` and `/metrics` respond in staging before promoting.

---

## 3. Health Checks & Smoke Tests

| Check | Command | Success Criteria |
| --- | --- | --- |
| HTTP health | `curl -sf http://$HOST:8000/health` | JSON reply with `"status":"ok"` and non-negative `uptimeSeconds`. |
| Metrics scrape | `curl -sf http://$HOST:8000/metrics | head` | Prometheus exposition with `mcp_http_requests_total`. |
| End-to-end parity | `pytest tests/e2e/test_end_to_end.py -k midazolam` | Pass within ~2 s; artefact produced in `reports/e2e/`. |
| Analyst console baseline | Use `/console`, capture + restore baseline | Snapshot recorded (audit event `simulation.snapshot.created`). |
| Async queue sanity | `make benchmark` (thread) or `make benchmark-celery` | P95s within performance-plan thresholds. |

Run these on every deploy and after any infrastructure maintenance.

---

## 4. Observability & Log Sampling

- **Structured logs:** JSON to stdout. Sample 20 lines with
  `jq '. | {ts:.timestamp, event:.event, status:.status_code}'`.
- **Correlation IDs:** Every request includes `X-Correlation-ID`.
- **Prometheus:** Alert on `mcp_http_request_duration_seconds_bucket` (P95) and
  `mcp_http_requests_total{status_code=~"5.."}`.
- **Audit trail:** `python -m mcp_bridge.audit.verify var/audit --fail-on-gap` to
  confirm hash chain.
- **Retention report:** `make retention-report` summarises artefact TTL policy.

---

## 5. Common Failure Modes

| Symptom | Likely Cause | Remediation |
| --- | --- | --- |
| `/run_simulation` stuck in `queued` | Worker offline or job backend misconfigured. | Check `JOB_BACKEND`; restart worker (`make celery-worker`) or API to reset thread pool. Inspect `var/jobs/registry.db` for job state. |
| Adapter errors referencing R libraries | `subprocess` backend missing ospsuite libs. | Validate `ADAPTER_OSPSUITE_LIBS`, `R_HOME`; run `python -m mcp_bridge.adapter.environment`. |
| Audit verification failures | Storage permissions or disk full. | Run `python -m mcp_bridge.audit.verify`, clear disk or move to S3 with object lock. |
| Analyst console cannot restore baseline | No snapshot recorded. | Use `POST /snapshot_simulation` before editing, or reload simulation to reset. |
| Prometheus metrics missing | Middleware disabled or endpoint blocked. | Ensure `/metrics` exposed and scraped; check `APP_CONFIG` for `adapter_to_thread` toggles. |

Escalate to platform engineering if remediation exceeds 15 minutes.

---

## 6. Rollback Strategy

1. Trigger `POST /snapshot_simulation` before applying bulk updates or agent
   automation.
2. Confirm snapshot via `GET /get_simulation_snapshot?simulationId=<id>`.
3. If rollback required: `POST /restore_simulation` (snapshot ID optional; uses
   latest when omitted).
4. Verify numeric parity with `calculate_pk_parameters` or parity suite.
5. Audit events `simulation.snapshot.created/restored` provide tamper evidence.

For infrastructure-level rollback, redeploy the previous container tag and rerun
the baseline tests listed in §3.

---

## 7. Drill Log (≤ 15 min mitigation)

| Date | Scenario | Duration | Notes |
| --- | --- | --- | --- |
| 2025-10-30 | Worker crash mid-simulation; restore baseline snapshot and replay job | 12 min | Verified via `pytest tests/e2e/test_end_to_end.py`, restored snapshot `sim-route@20251030T120501Z`. |

Document future drills here. Drills older than six months should be refreshed.

---

## 8. Useful Commands

```bash
# Structured log tail
journalctl -u mcp-bridge.service -f | jq

# Force Celery job sync of external IDs
python - <<'PY'
from mcp_bridge.services.job_service import DurableJobRegistry
registry = DurableJobRegistry('var/jobs/registry.json')
print(len(registry.load_all()))
PY

# Snapshot API examples
http POST :8000/snapshot_simulation simulationId==demo-sim
http POST :8000/restore_simulation simulationId==demo-sim snapshotId==20251030T120501000Z
```

---

## 9. References

- [Performance plan](../mcp-bridge/performance-plan.md)
- [HPC submission stub](hpc.md)
- [Change management checklist](../mcp-bridge/operations/change-management.md) *(pending Task 56)*

Keep this runbook version-controlled. Any incident reviews should update the
relevant sections within 24 hours.
