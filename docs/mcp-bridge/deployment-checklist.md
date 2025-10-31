# Deployment Checklist

Use this checklist prior to promoting the MCP Bridge into staging or production.

## Configuration

- [ ] `ENVIRONMENT` is set to `staging` or `production` as appropriate.
- [ ] `AUTH_DEV_SECRET` is **unset**; production deployments rely on OIDC/JWT validation via `AUTH_ISSUER_URL`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`.
- [ ] Job backend (`JOB_BACKEND`) is configured for the target environment (`thread` for single-instance, `celery` with Redis/RabbitMQ for distributed execution).
- [ ] Celery settings are defined when `JOB_BACKEND=celery` (broker URL, result backend, TLS credentials, eager mode disabled).
- [ ] `JOB_REGISTRY_PATH` resolves to a persistent volume that survives API restarts (shared if multiple API replicas run concurrently).
- [ ] `MCP_MODEL_SEARCH_PATHS` points to the approved model directory whitelist for the deployment.
- [ ] Audit backend configured (`AUDIT_STORAGE_BACKEND=local|s3`) with required S3 parameters when applicable (bucket, prefix, region, Object Lock mode, retention days).

## Secrets & Identity

- [ ] Application secrets live in the environment/secrets manager (not committed to git).
- [ ] IdP client credentials are rotated per policy and accessible to the deployment pipeline.
- [ ] OAuth scopes/roles issued by the IdP map cleanly to MCP roles (`viewer`, `operator`, `admin`).

## Observability & Audit

- [ ] Audit trail storage (`AUDIT_STORAGE_PATH` or WORM backend) is configured and writable.
- [ ] Job telemetry dashboards/alerts are configured for the selected job backend (Celery worker health, queue depth, job failures).
- [ ] Celery event/metrics collection is enabled (Flower, Prometheus exporter, or equivalent) with alert thresholds for queue age and worker liveness.
- [ ] Structured logs forward to the central logging platform with correlation IDs enabled.

## Runbooks & Tooling

- [ ] Operations team reviewed `docs/mcp-bridge/operations/celery-runbook.md` and `docker-compose.celery.yml`.
- [ ] On-call rotation updated with incident response steps for worker crashes and broker outages.
- [ ] WORM audit runbook acknowledged; retention/restore SOPs documented for the selected S3 bucket.
- [ ] Audit operations runbook (`docs/mcp-bridge/operations/audit-runbook.md`) reviewed and linked in ops wiki.

## Checklist Runbook

1. Verify configuration: run `python -m mcp_bridge.config` (future CLI) or smoke test `AppConfig.from_env()` in the deployment environment.
2. Execute `make check` and `make compliance` in the pipeline; both must pass.
3. For Celery deployments, start the compose stack (`docker compose -f docker-compose.celery.yml up`) or equivalent orchestrated resources; confirm `/jobs/{id}/events` streams job state transitions.
4. Trigger a smoke workflow (load → set → run) against staging, review audit log output, and sign off before promoting to production.
