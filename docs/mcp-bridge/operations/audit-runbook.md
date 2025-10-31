# Audit Trail Operations Runbook

This runbook documents day-to-day operations for the immutable audit trail,
covering both local JSONL storage and S3 Object Lock deployments.

## 1. Configuration Summary

| Variable | Description |
| --- | --- |
| `AUDIT_ENABLED` | Enables/disables audit recording (must be `true` in production). |
| `AUDIT_STORAGE_BACKEND` | `local` (JSONL on disk) or `s3` (Object Lock bucket). |
| `AUDIT_STORAGE_PATH` | Local directory used when backend is `local`. |
| `AUDIT_S3_BUCKET` / `AUDIT_S3_PREFIX` | Target bucket & key prefix for S3 backend. |
| `AUDIT_S3_REGION` | Optional region override; defaults to client configuration. |
| `AUDIT_S3_OBJECT_LOCK_MODE` | `governance` or `compliance` when using Object Lock. |
| `AUDIT_S3_OBJECT_LOCK_DAYS` | Retention period applied to each object (days). |
| `AUDIT_S3_KMS_KEY_ID` | Optional KMS key used for encryption at rest. |
| `AUDIT_VERIFY_LOOKBACK_DAYS` | Window (days) verified by the scheduled integrity job. |

Object Lock considerations:

- Configure the bucket with Object Lock enabled at creation time.
- IAM policies must allow `PutObject` with Object Lock parameters and (optionally) `WriteGetObject` for KMS keys.
- Retention periods set in configuration should meet compliance policy; increases require approvals.

## 2. Verification Workflow

### Scheduled job (recommended)

Run the packaged helper daily (or more frequently) in CI/cron:

```bash
python -m mcp_bridge.audit.jobs
```

This loads `AppConfig`, computes the verification window using
`AUDIT_VERIFY_LOOKBACK_DAYS`, and verifies:

1. Hash chain continuity across all events in the window.
2. For S3 backends: Object Lock mode matches expectation and retain-until dates
   are at least the configured number of days beyond the newest event in each object.

Failures exit non-zero with a descriptive message. Integrate with alerting so
operators receive immediate notification when the check fails.

### Manual verification

- **Local storage**

  ```bash
  python -m mcp_bridge.audit.verify var/audit --start 2025/10/24 --end 2025/10/25
  ```

- **S3 Object Lock**

  ```bash
  python -m mcp_bridge.audit.verify s3://$AUDIT_S3_BUCKET/$AUDIT_S3_PREFIX \
    --object-lock-mode $AUDIT_S3_OBJECT_LOCK_MODE \
    --object-lock-days $AUDIT_S3_OBJECT_LOCK_DAYS \
    --start 2025/10/24 --end 2025/10/25
  ```

Run manual checks ahead of audits, after bucket configuration changes, or
following incident remediation.

## 3. Key Rotation & Access Management

### KMS key rotation

- Rotate `AUDIT_S3_KMS_KEY_ID` via AWS KMS automatic rotation or manual key swap.
- If migrating to a new KMS key: update secrets/config, deploy the service, and
  run the scheduled verification job to ensure new objects are still valid.
- Retain access to prior keys until all retained audit objects expire.

### IAM permissions

- Ensure automation users have `s3:PutObject`, `s3:GetObject`,
  `s3:GetObjectRetention`, `s3:GetObjectLegalHold`, and (for governance mode)
  `s3:BypassGovernanceRetention` if needed by incident workflows.
- Use least privilege: restrict prefixes to the audit namespace.

## 4. Incident Response

### Hash mismatch / verification failure

1. Quarantine affected objects (copy to forensic bucket). Do **not** delete.  
2. Re-run verification to identify the earliest failing event.
3. Escalate to compliance/infosec. Investigate source logs, application logs,
   and AWS CloudTrail for tamper evidence.  
4. If corruption is isolated or due to a partial write, restore from the last
   known good backup.

### Missing Object Lock metadata

1. Confirm bucket configuration (Object Lock mode & retention).  
2. Validate IAM policies; ensure clients can specify Object Lock headers.  
3. Retry uploads; if failures persist, disable mutating operations (`AUDIT_ENABLED=false`)
   until remediation to avoid unlogged activity.

### Restore / audit replay

- Use versioned backups or cross-region replication to recover deleted objects.  
- Replay events with `python -m mcp_bridge.audit.verify --start ... --end ...`
  to ensure chain continuity post-restore.
- Document the incident in ops records with verification logs attached.

## 5. Operational Checklist

- [ ] Daily scheduled verification (`python -m mcp_bridge.audit.jobs`) succeeds, results archived.  
- [ ] Weekly manual verification of full month (rotating window) completed.  
- [ ] Monthly review of retention settings vs. policy; update `AUDIT_S3_OBJECT_LOCK_DAYS` if required.  
- [ ] KMS key rotation status checked quarterly; update `AUDIT_S3_KMS_KEY_ID` when rotating keys.  
- [ ] Permissions audit: confirm only authorised roles can access audit buckets.  
- [ ] Disaster recovery drill annually: restore sample objects from backup and verify hash chain.

## 6. References

- `python -m mcp_bridge.audit.jobs` – scheduled verification helper.  
- `python -m mcp_bridge.audit.verify` – manual hash/retention verifier.  
- `docs/mcp-bridge/audit-trail.md` – architecture and testing guidelines.  
- `docs/mcp-bridge/deployment-checklist.md` – deployment prerequisites.
