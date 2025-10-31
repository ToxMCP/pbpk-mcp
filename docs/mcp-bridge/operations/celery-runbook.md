# Celery Operations Runbook

This runbook covers day‑to‑day operations for the Celery job backend that
powers long-running PBPK simulations. Use it alongside the architecture
overview in `docs/mcp-bridge/distributed-job-architecture.md`.

## 1. Prerequisites

- `JOB_BACKEND=celery` is set for the API process.
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` point to the same broker
  (Redis or RabbitMQ) for the API and worker containers.
- `JOB_REGISTRY_PATH` resolves to a writable, persistent location shared across
  API restarts (e.g., bind-mounted volume or network share).
- Session registry is configured appropriately: `SESSION_BACKEND=redis` with a
  reachable `SESSION_REDIS_URL` so API pods share simulation handles.
- Workers and API processes run identical container images so the ospsuite
  toolchain stays in sync.
- For Object Lock deployments, ensure `AUDIT_STORAGE_BACKEND=s3` and related
  S3/Object Lock settings are present in the environment.

## 2. Deployment Workflow

1. **Prepare configuration**
   - Ensure `.env` (or secrets manager) defines Celery broker/result URLs,
     disables eager mode, and sets an explicit `JOB_REGISTRY_PATH`.
   - Provision Redis/RabbitMQ with TLS and authentication as required by
     infrastructure policy.
2. **Launch infrastructure**
   - Use the reference compose file:
     ```bash
     docker compose -f docker-compose.celery.yml up -d
     ```
     This starts the API, Celery worker, and Redis with a shared `var/`
     volume that stores the audit trail and job registry JSON.
3. **Smoke test**
   - `make benchmark` exercises the smoke scenario against the running stack.
   - `python -m mcp_bridge.benchmarking --transport http --iterations 1`
     confirms the HTTP transport path and job completion.
4. **Rolling restarts**
   - Restart workers first (`docker compose restart worker`) so new jobs
     continue executing while the API reloads the registry file.
   - Verify `/mcp/capabilities` and `/get_job_status` respond after restarts.

## 3. Scaling Guidance

- **Horizontal workers**: add Celery worker replicas (`docker compose up -d --scale worker=3`)
  or deploy additional worker pods in Kubernetes. Increase concurrency via
  `CELERY_WORKER_CONCURRENCY` or `--concurrency` flag.
- **Queue partitioning**: use Celery routing keys if population workloads need dedicated queues.
- **Job registry volume**: ensure the API pod has exclusive write access; use a
  read-write-many volume if multiple API replicas are deployed.

## 4. Monitoring & Alerting

- Enable Celery events (`celery -E`) and expose metrics via Flower or custom exporter.
- Track key signals:
  - Queue depth and job age (alert when queue wait exceeds SLA).
  - Worker heartbeats / liveness (alert on worker offline for >60 seconds).
  - Broker connectivity errors and retry loops (log level `warning` or higher).
  - Audit trail entries (`var/audit/*.jsonl`) for succeeded/failed jobs aligned with Celery transitions.
- Integrate with existing Prometheus/Grafana dashboards; the runbook links to
  dashboards once provisioned.

## 5. Incident Response

### Worker Crash

1. Inspect worker logs (`docker compose logs worker`).
2. Restart the worker container; Celery requeues in-flight jobs unless marked
   as acknowledged.
3. Check the audit trail for partial jobs and re-submit if required.

### Broker Outage

1. Bring broker back online; Celery retries until connection succeeds.
2. Confirm API health (`/health`) and list queued jobs with `celery -A mcp_bridge.services.celery_app.celery_app inspect active`.
3. Verify the job registry file is intact; remove any truncated `.tmp` files.

### Stuck Jobs

1. Use `/jobs/{id}/events` SSE stream to confirm status transitions.
2. Cancel via `/mcp/jobs/{id}/cancel` (if exposed) or `celery control revoke <id> --terminate`.
3. Update the job registry manually only as a last resort; prefer requeueing the task.

### Registry Corruption

1. Stop the API process.
2. Restore the latest backup of `JOB_REGISTRY_PATH` (or remove the file to force rebuild from Celery state).
3. Restart the API; it resyncs job states from Celery on boot.

## 6. Periodic Maintenance

- Rotate `var/audit` and `var/jobs/registry.json` using logrotate or S3 archival.
- Verify Celery broker backups and persistence (Redis AOF/RDB snapshots).
- Run `python -m mcp_bridge.runtime.session_cli prune-stale` weekly to remove
  orphaned session identifiers and `dump` for health checks.
- Review retry statistics weekly to tune `JOB_MAX_RETRIES` and Celery retry policies.

## 7. Checklist Before Production Changes

- ✅ Configuration validated (`AppConfig.from_env()` run in staging).
- ✅ Celery worker capacity scaled for expected load.
- ✅ Monitoring dashboards updated and alerts armed.
- ✅ Smoke benchmarks captured pre/post change and stored in `var/benchmarks/`.
- ✅ Incident contacts updated in on-call docs.
