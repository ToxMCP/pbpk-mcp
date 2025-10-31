# HPC Submission Stub

This document explains the mocked Slurm integration that satisfies Task 50 ("HPC submission stub") and provides the artefacts required for future production hardening.

## Why the stub exists

- Bridges the MCP bridge job layer to a simulated batch scheduler so we can exercise external job identifiers, queue delays, and audit provenance without needing a real Slurm cluster.
- Validates the durability back-end changes (extra `external_job_id` column) and ensures `/get_job_status` now exposes an `externalJobId` field.
- Provides a repeatable regression (`pytest -m hpc_stub` / `make test-hpc`) that runs in CI to guard the integration.

## Enabling the stub in any environment

| Setting | Description | Default |
| --- | --- | --- |
| `JOB_BACKEND=hpc` | Switches `create_job_service` to the stub scheduler. | `thread` |
| `JOB_REGISTRY_PATH` | SQLite file for durable state (`external_job_id` persisted here). | `var/jobs/registry.json` |
| `HPC_STUB_QUEUE_DELAY_SECONDS` | Artificial delay before the stub dispatches work to the local executor. | `0.5` |

Example local run:

```bash
export JOB_BACKEND=hpc
export HPC_STUB_QUEUE_DELAY_SECONDS=0.1
uvicorn mcp_bridge.app:create_app --reload --factory
```

Once enabled, `/get_job_status` responses include `externalJobId` alongside the usual MCP metadata, and audit events are enriched with the Slurm-style identifier.

## Execution flow

1. **Submit** – `JobService.submit_*` enqueues the job and hands control to `StubSlurmScheduler`.
2. **External ID assignment** – the scheduler issues an ID of the form `SLURM-XXXXXX`, calls `assign_external_job_id`, and emits `job.<type>.hpc_submitted`.
3. **Queue delay** – the stub sleeps for the configured delay to mimic `sbatch` wait time.
4. **Dispatch** – after the delay an audit event `job.<type>.hpc_dispatched` is recorded and the local executor begins `run_simulation_sync`/`run_population_simulation_sync`.
5. **Completion** – existing logic marks the job `succeeded/failed/timeout` and standard audit hooks capture the terminal event.

All audit records include the external identifier so that compliance teams can correlate MCP jobs with Slurm accounting data when the real integration arrives.

## Mocked CI gate

- **Test location:** `tests/unit/test_hpc_stub.py`
- **Marker:** `@pytest.mark.hpc_stub`
- **Command:** `make test-hpc`
- **Coverage:** Confirms that the stub assigns an external job id, transitions to `SUCCEEDED`, and emits the audit events described above.

The test uses the real `DurableJobRegistry`/`AuditTrail` to ensure migrations and hash chaining continue to work with the new fields.

## Operational notes

- The stub joins its background threads during shutdown to prevent dangling workers when the API exits.
- Monitoring/alerting should watch for `job.*.hpc_dispatched` without a matching terminal status; that indicates a scheduler -> executor hand-off problem.
- Production Slurm/LSF adapters can replace the stub by implementing the same `JobScheduler` protocol exposed in `mcp_bridge.services.job_service.JobScheduler`.
