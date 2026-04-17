# Release Readiness

This note is the short maintainer-facing release gate for the current PBPK MCP line.

Use it together with:

- `docs/github_publication_checklist.md` for the broader publish checklist
- `docs/post_release_audit_plan.md` for the Day 0 / Day 7 / Day 30 follow-up audit
- `docs/hardening_migration_notes.md` for trust-surface and audit-storage caveats that must stay accurate at release time
- `docs/github_branch_protection.md` for the intended GitHub enforcement model on `main`
- `docs/deployment/s3_object_lock_audit.md` for the operator-grade off-host audit path

## Required Gates

- `python3 scripts/public_release_preflight.py --auth-dev-secret pbpk-local-dev-secret-32bytes-long`
- normal `CI` must pass, including the retained runtime-contract `sdist`, wheel, and report artifact
- `python3 scripts/release_readiness_check.py`
- `make misuse-prevention-test PY=python3`
- `python3 scripts/validate_model_manifests.py --strict --require-explicit-ngra --curated-publication-set`
- `python3 scripts/generate_regulatory_goldset_audit.py --check`
- `python3 scripts/check_release_metadata.py`
- the live GitHub `main` ruleset must match `docs/github_branch_protection.md` before tagging or public merge

## Required Release-Prep Evidence

The recommended maintainer entrypoint is `scripts/public_release_preflight.py`. It waits for a running local stack, executes the runtime-contract gate, reruns the live release-readiness check, runs the named live-stack pytest slice, executes deterministic and population workspace smoke checks, and performs a dry-run review-signoff index audit against the configured audit store.

Retain the local summary emitted by that entrypoint:

- `var/public_release_preflight_summary.json`
  - require `overallStatus = passed`
  - keep the file with the rest of the release evidence when preparing a public tag

- run the repository `Release Artifacts` workflow and retain:
  - validated `sdist`
  - validated wheel
  - `release-artifact-report.json`
- run the repository `Model Smoke` workflow and retain:
  - `var/public_release_preflight_summary.json`
  - `var/release_readiness_summary.json`
  - `var/workspace_model_smoke_report.json`
  - `var/workspace_model_smoke_rxode2_report.json`
  - `var/public_release_preflight_stdout.txt`
  - compose diagnostics

## GitHub Enforcement Prerequisite

Before public release, confirm the live repository settings, not only the repo files:

- `main` is protected by an active ruleset
- pull requests are required for merges to `main`
- code-owner review is required
- `CI` is a required passing check
- force-push is blocked on `main`
- the bypass list is empty, or any exception is documented explicitly in release notes

## Minimum Claims Before Tagging

- published contract artifacts match the packaged wheel boundary
- bundled example models still pass the curated-publication NGRA gate
- README positioning still matches the actual runtime and trust surface
- audit-backed sign-off language stays descriptive and does not imply override authority
- the current audit-storage boundary remains accurately documented for local versus S3-backed deployments
- the intended branch-protection and code-owner review model is still represented accurately in repo docs
- the live GitHub ruleset still matches the documented enforcement model

## Block Release If

- the runtime-contract report, release-artifact report, or model smoke artifacts are missing
- packaged contract files diverge from the published docs or schema bundle
- bundled example models regress to implicit workflow role, population support, evidence basis, or claim boundaries
- README or release docs overstate local audit retention or decision authority
- live smoke or release-readiness checks fail on the packaged local stack
- the retained `public_release_preflight_summary.json` does not show a passing end-to-end result
