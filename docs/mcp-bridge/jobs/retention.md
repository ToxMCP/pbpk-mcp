# Artefact Retention & TTL Policy

This note captures how long the MCP bridge persists asynchronous job metadata,
population-simulation artefacts, and agent state. Use it when planning storage
budgets or validating that clean-up jobs are working as expected.

## Defaults

| Artefact | Setting | Default | Notes |
| --- | --- | --- | --- |
| Job metadata & simulation results | `JOB_RETENTION_SECONDS` | 604800 (7 days) | Applies to the durable job registry (queued/running/completed records) and any persisted single-subject results cached by the adapter. |
| Population chunks | `POPULATION_RETENTION_SECONDS` | 604800 (7 days) | Governs how long claim-check artefacts remain on disk. |
| Agent checkpointer | `AGENT_CHECKPOINTER_PATH` | `var/agent/checkpoints.sqlite` | SQLite file storing LangGraph thread state; retained indefinitely until rotated manually. |
| Audit trail | see `docs/mcp-bridge/audit-trail.md` | Deployment-specific | Separately configured WORM retention (local filesystem or S3 Object Lock). |

All durations are expressed in seconds. Set the value to `0` to disable
automatic purging for that artefact (not recommended for production).

## Enforcement

- The job service calls `_apply_retention_policy()` after every transition
  (submission, completion, cancellation, periodic polls). Stale records and
  associated results are deleted once they fall outside the retention window.
- `PopulationResultStore.purge_expired()` prunes chunk directories older than
  the configured population-retention window.
- The LangGraph agent uses a persistent SQLite checkpointer by default.
  Production deployments should back up or rotate `var/agent` according to the
  organisation’s data-governance policy.

Run `make retention-report` to generate a JSON report summarising artefacts that
were purged during the most recent cycle. The report lives under
`var/reports/retention/` and can be archived for compliance evidence.

## Operational Checklist

1. **Before go-live** – set retention windows that align with regulatory needs
   (e.g., extend to 30 days if analysts revisit past runs frequently).
2. **Monitoring** – export Prometheus metrics for `mcp_job_retained_total`
   (planned) or parse the retention report in CI to ensure purges occur.
3. **Agent continuity** – include `var/agent/checkpoints.sqlite` in backup
   plans; losing this file resets LangGraph threads and their confirmation
   history.
4. **Security posture** – restrict write access to retention directories and
   ensure the purge job runs under a privileged account to avoid partial deletes.
