# Change Management Checklist

This checklist governs MCP bridge changes that reach shared environments
(staging, pre-prod, production). It complements the service runbook and is
enforced via the pull request template.

---

## 1. Scope

- Application code, adapter changes, or infrastructure manifests deployed to
  shared environments.
- Configuration updates affecting job backends, adapter runtime, or security
  posture.
- Documentation-only changes may skip smoke benchmarks but must confirm no
  operational impact.

---

## 2. Required Evidence

| Item | Description | How to record |
| --- | --- | --- |
| Smoke benchmark | Run `make benchmark` (thread) or `make benchmark-celery` (Celery) and record latency output. | Paste command + summary and attach artefact path (e.g. `var/benchmarks/*.json`). |
| Alert verification | Demonstrate key alerts are armed (SLO, error rate). For Prometheus, use `amtool` or staging alert test; for other systems, capture screenshot/log. | Note the alert ID / screenshot link in PR checklist. |
| Runbook impact | Confirm whether `docs/operations/runbook.md` requires updates. | Tick “not required” or link PR snippet. |
| Test results | `pytest` (or targeted suites) and any additional validation steps. | Provide command + status. |

All evidence is tracked in the PR description using the template checkboxes.

---

## 3. Workflow

1. **Before opening PR**
   - Run unit tests locally (`pytest`).
   - Execute relevant smoke benchmark; save artefacts.
   - Validate alerts (e.g., trigger a staging alert test or confirm dashboards).

2. **During review**
   - Fill out the PR checklist with evidence links.
   - Reviewers must verify artefacts before approving.

3. **Before merge / deploy**
   - Ensure checklist remains accurate if code changes during review.
   - Re-run smoke tests if changes materially affect performance or ops.

4. **Post-deploy**
   - Spot-check `/health` and `/metrics`.
   - Update drill log in runbook if an incident or mitigation exercise occurred.

---

## 4. Tooling

- **Benchmarks**: `make benchmark`, `make benchmark-celery`.
- **HPC stub**: `make test-hpc` when changes touch the stub scheduler.
- **Retention**: `make retention-report` for artefact governance.
- **Alerts**: use Prometheus Alertmanager (`amtool silence query`) or service-specific tooling to verify status.

Store output in `var/benchmarks/`, `var/reports/`, or attach screenshots in the
PR as appropriate.

---

## 5. Exceptions

Exceptions require platform lead approval and must be documented in the PR with
mitigation steps. Emergency fixes still need a post-mortem and checklist update
within 24 hours.

---

## 6. References

- [Service Runbook](../../operations/runbook.md)
- [HPC Stub Guide](../../operations/hpc.md)
- [PR Template](../../../.github/pull_request_template.md)

Keep this document synced with process changes communicated via platform
engineering.
