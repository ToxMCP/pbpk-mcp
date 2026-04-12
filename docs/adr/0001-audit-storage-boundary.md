# ADR 0001: Audit Storage Boundary

- Status: Accepted
- Date: 2026-04-08

## Context

PBPK MCP now exposes reviewer-readable sign-off history through `/review_signoff/history` and records
hash-chained audit events for sign-off, rejection, and revocation flows.

The workspace currently supports two materially different audit-storage modes:

- local filesystem JSONL files through `LocalAuditTrail`
- S3 objects through `S3AuditTrail`, with optional Object Lock and KMS settings

Reviewers can easily over-read "viewer-readable immutable history" as "externally retained immutable
archive." That would be inaccurate for the default local deployment profile.

## Decision

Keep the local filesystem audit backend as the default for local compose and maintainer workflows, but
document the boundary explicitly:

- local audit storage is reviewable and hash-chained
- local audit storage is not the same thing as off-host immutable retention
- higher-assurance deployments should use the S3 backend with Object Lock expectations and external
  retention discipline

## Consequences

Positive:

- local bring-up stays simple and cloud-independent
- reviewers still get a readable, hash-linked event history in the default stack
- the stronger S3 path remains available without forcing it onto every developer workflow

Negative:

- local audit guarantees are limited by filesystem durability and backup practice
- teams must not treat `/review_signoff/history` alone as proof of external retention
- release evidence handling still needs an explicit retention workflow outside the default local stack

## Operational Notes

- Verify local audit history with `python -m mcp_bridge.audit.verify var/audit`.
- Verify S3-backed audit history with `python -m mcp_bridge.audit.verify s3://<bucket>/<prefix>`.
- When S3 Object Lock is part of the deployment contract, verify it explicitly with
  `--object-lock-mode` and `--object-lock-days`.
