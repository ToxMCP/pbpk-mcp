# Artefact Retention & Integrity Policy

## Scope

This policy applies to artefacts stored under the `var/` directory (e.g., parity results,
benchmarks, audit trail snapshots) and any long-term compliance payloads.

## Retention Windows

| Artefact class                  | Location                        | Retention | Notes |
|---------------------------------|---------------------------------|-----------|-------|
| Audit trail JSONL               | `var/audit/`                    | 365 days  | Rolled up into immutable S3 storage if enabled. |
| Benchmark artefacts             | `var/benchmarks/`               | 90 days   | Old runs pruned via scheduled job; current baseline retained indefinitely. |
| Population simulation outputs   | `var/population-results/`       | 30 days   | Summaries kept, raw chunks removed after expiry. |
| Retention reports               | `var/reports/retention/`        | 365 days  | Provides evidence for governance reviews. |

## Integrity Checks

- Monthly job executes `make retention-report` to hash all artefacts and generate
  `var/reports/retention/report.json`.
- Reports enumerate path, size, SHA-256 digest, and last modified time and are
  archived alongside internal compliance documentation.
- Spot checks compare successive reports to ensure unexpected mutations are detected.

## Automation

1. **Monthly report generation** (cron or CI schedule):
   ```
   make retention-report
   git add var/reports/retention/report.json
   git commit -m "chore: update retention report"
   ```
2. **Cleanup job**: administrative script removes expired files according to the
   retention windows. Deleted artefacts are logged to the audit trail.

## Review

- Policy reviewed quarterly by the compliance lead.
- Changes recorded in the governance changelog and circulated to stakeholders.
