# S3/Object-Lock Audit Deployment

The default local stack writes the audit trail to the local filesystem under `var/audit`. That is useful for reviewability and smoke checks, but it is not the strongest retention path.

For stronger operator-grade retention, use the S3 audit backend with bucket-level Object Lock and external retention discipline.

## Environment Contract

The runtime already supports these settings:

- `AUDIT_STORAGE_BACKEND="s3"`
- `AUDIT_S3_BUCKET`
- `AUDIT_S3_PREFIX`
- `AUDIT_S3_REGION`
- `AUDIT_S3_OBJECT_LOCK_MODE`
- `AUDIT_S3_OBJECT_LOCK_DAYS`
- `AUDIT_S3_KMS_KEY_ID`
- `AUDIT_VERIFY_LOOKBACK_DAYS`

The packaged hardened deployment path also forwards these variables through `docker-compose.hardened.yml`, so `./scripts/deploy_hardened_stack.sh` can use the S3/Object Lock backend without local compose edits.

For local S3-compatible smoke runs, the runtime also accepts:

- `AUDIT_S3_ENDPOINT_URL`
- `AUDIT_S3_FORCE_PATH_STYLE`

Recommended values:

```env
AUDIT_ENABLED=true
AUDIT_STORAGE_BACKEND="s3"
AUDIT_S3_BUCKET="pbpk-mcp-audit"
AUDIT_S3_PREFIX="bridge/audit"
AUDIT_S3_REGION="eu-west-1"
AUDIT_S3_OBJECT_LOCK_MODE="governance"
AUDIT_S3_OBJECT_LOCK_DAYS=90
AUDIT_S3_KMS_KEY_ID="arn:aws:kms:REGION:ACCOUNT:key/..."
AUDIT_VERIFY_LOOKBACK_DAYS=1
```

## Preconditions

Before turning this on:

- create the bucket with Object Lock enabled
- define the retention mode and retention period outside the application as bucket policy / operational policy
- ensure the runtime identity can `PutObject`, `GetObject`, and `ListBucket` on the selected prefix
- if KMS is used, ensure the runtime identity can encrypt and decrypt with the configured key

This MCP can request Object Lock headers during writes, but it does not create or govern the bucket-level retention model for you.

## Verification Steps

After deployment:

1. record a trust-bearing event such as operator review sign-off
2. verify viewer-readable history still works through `/review_signoff/history`
3. verify sign-off summaries still appear on trust-bearing tool outputs
4. run `python3 scripts/release_readiness_check.py` against the deployed stack
5. inspect the bucket objects and confirm the expected Object Lock mode/retention is present

If the bucket or local audit store already contains older sign-off events from before the dedicated sign-off index existed, run:

- `python3 scripts/backfill_review_signoff_index.py var/audit`
- `python3 scripts/backfill_review_signoff_index.py s3://<bucket>/<prefix> --region <region>`

Use `--endpoint-url` and `--force-path-style` for local S3-compatible backends such as MinIO.

## Local S3-Compatible Smoke

For a local packaged-stack smoke run against MinIO:

1. run `./scripts/deploy_s3_audit_smoke_stack.sh`
2. run `python3 scripts/s3_audit_smoke.py --auth-dev-secret pbpk-local-dev-secret-32bytes-long`

That path proves the S3 backend plumbing, viewer-readable sign-off history, trust-bearing sign-off augmentation, and hash-chain verification against a local S3-compatible endpoint. It does not prove real AWS bucket governance or production Object Lock administration.

## What This Changes

Using the S3 backend should not change the trust-bearing payload shape. The difference is retention posture:

- local backend: reviewable and hash-chained, but local-storage retention only
- S3/Object-Lock backend: off-host retention path suitable for stronger audit discipline

## Boundary Reminder

This improves retention and audit durability. It does not change:

- qualification state
- operator sign-off semantics
- claim boundaries
- scientific adequacy
