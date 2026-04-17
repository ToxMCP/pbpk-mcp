# Contributing

Thanks for contributing to PBPK MCP.

## Scope

This repository is a public PBPK MCP server with a published contract surface, live runtime checks, and release evidence gates. Contributions should preserve:

- contract clarity
- conservative scientific boundaries
- explicit auth and runtime safety
- reproducible release behavior

## Local Setup

Start from a clean clone of the published repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

If your system Python has a broken `build` entrypoint, prefer `.venv/bin/python` for packaging and release-readiness checks.

## Common Checks

Use the lightest check set that matches the scope of the change:

- docs-only or small code changes:
  - `make lint`
  - run the targeted unit tests for the files you changed
- contract, schema, trust-surface, or packaging changes:
  - `make runtime-contract-test`
- release-facing changes:
  - `python3 scripts/release_readiness_check.py`
  - `.venv/bin/python scripts/check_distribution_artifacts.py --artifact-dir dist --report-path dist/runtime-contract-report.json`

The normal GitHub workflows are intentionally split:

- `CI` is the fast contributor gate and now retains a validated wheel, `sdist`, and runtime-contract report
- `Model Smoke` is the slower live-stack and worker-image gate
- `Release Artifacts` is the retained release-package gate for tags and release prep

## Pull Requests

Before opening a pull request:

- run the relevant local tests for the area you changed
- update docs when behavior, contracts, or workflow expectations change
- avoid widening scientific or regulatory claims without explicit evidence and matching tests
- keep temporary files, credentials, machine-local paths, and generated runtime artifacts out of the patch
- expect code-owner review for merges to `main`; the repository designates `@senseibelbi` in `.github/CODEOWNERS`

For release-facing or trust-surface changes, review:

- `docs/release_readiness.md`
- `docs/github_branch_protection.md`
- `docs/github_publication_checklist.md`
- `docs/hardening_migration_notes.md`
- `docs/deployment/s3_object_lock_audit.md`
- `docs/pbk_reviewer_signoff_checklist.md`
- `docs/post_release_audit_plan.md`

## Model And Contract Changes

If you change:

- MCP tools or routes
- public schemas or examples
- trust-bearing summaries
- release or readiness checks

also update the matching tests and generated contract artifacts.

## Security And Scientific Claims

Do not:

- commit secrets, bearer tokens, or local credentials
- present runtime readiness as scientific adequacy
- present illustrative examples as regulatory-ready evidence
- remove caveats, block reasons, or scope boundaries from trust-bearing outputs without replacing them with something stronger

## Communication

Use the GitHub issue templates for normal bugs and documentation/reviewability gaps, and use the pull-request template when opening code changes. GitHub branch protection should require code-owner review before merges to `main`. For sensitive security problems, follow `SECURITY.md` instead of opening a public issue with exploit details.

If your change touches the sensitivity workflow or OSPSuite population planning, keep the design notes in `docs/architecture/sensitivity_v2.md` and `docs/architecture/ospsuite_population_feasibility.md` accurate as well.
