# GitHub Publication Checklist

## Before Push

- review `docs/hardening_migration_notes.md` and confirm client-facing migration notes still match the release
- review `docs/release_readiness.md` and confirm the required gates and retained artifacts still match the active workflows
- review `docs/github_branch_protection.md` and confirm the intended `main` ruleset is still the one you want enforced publicly
- review `docs/pbpk_model_onboarding_checklist.md` and confirm the recommended trust pipeline still matches the current MCP surfaces
- review `docs/pbk_reviewer_signoff_checklist.md` and confirm sign-off language still matches the actual operator workflow
- review `docs/post_release_audit_plan.md` and confirm the first post-release audit owner/date are assigned
- review `benchmarks/regulatory_goldset/regulatory_goldset_summary.md` and confirm the benchmark-derived MCP gap list still matches the intended release positioning
- confirm the README reflects the intended public positioning
- confirm the release version and docs are aligned
- confirm no local runtime artifacts are being committed
- confirm example models included in the repo are intended for public distribution
- confirm no internal test-model assets or study-specific generated artifacts remain in the public release surface unless they are explicitly intended for public distribution
- confirm no credentials, tokens, or machine-specific paths remain in docs or scripts
- confirm the live GitHub `main` ruleset is active and matches `docs/github_branch_protection.md`
- confirm the ruleset bypass list is empty, or that any remaining bypass is explicitly accepted for this release
- run `python3 -m unittest -v tests/test_oecd_bridge.py`
- run `python3 -m unittest -v tests/test_load_simulation_contract.py`
- run `python3 -m unittest -v tests/test_model_manifest.py`
- run `python3 -m unittest -v tests/test_trust_surface.py`
- run `python3 -m unittest -v tests/test_model_discovery_live_stack.py`
- run `python3 -m unittest -v tests/test_oecd_live_stack.py`
- run `python3 scripts/check_release_metadata.py`
- run `python3 scripts/generate_regulatory_goldset_audit.py --check`
- run `make misuse-prevention-test PY=python3`
- run `python3 scripts/validate_model_manifests.py --strict --require-explicit-ngra --curated-publication-set`
- run `python3 scripts/public_release_preflight.py --auth-dev-secret pbpk-local-dev-secret`
- retain `var/public_release_preflight_summary.json` and confirm it ends with `overallStatus = passed`
- run `python3 scripts/release_readiness_check.py`
- run `python3 scripts/workspace_model_smoke.py --auth-dev-secret pbpk-local-dev-secret`
- run `python3 scripts/workspace_model_smoke.py --include-population --auth-dev-secret pbpk-local-dev-secret`
- if preparing a release, run the repository `Model Smoke` workflow and keep the uploaded smoke JSON artifact with the release evidence
  - confirm the uploaded artifact includes `var/public_release_preflight_summary.json`
- if preparing a release tag, run the repository `Release Artifacts` workflow and retain the uploaded `sdist`/`wheel` bundle plus `release-artifact-report.json` with the release evidence

## Public Positioning

- describe PBPK MCP as one user-facing MCP with multiple execution backends
- state clearly that `rxode2` is a direct execution backend for PBPK R models
- state clearly that Berkeley Madonna `.mmd` is a conversion source, not a runtime format
- state clearly that `.pksim5` is an export source and should be converted to `.pkml` before runtime use
- state clearly that runnable does not mean scientifically qualified
- state clearly that OECD-oriented metadata supports risk-assessment workflows but does not replace scientific dossier review
- state clearly when the local runtime still relies on source overlays rather than a fully packaged image/runtime boundary
- state clearly that JSON-RPC capability discovery uses a REST companion resource surface rather than in-band JSON-RPC resources

## Files To Review Before Publishing

- `README.md`
- `CHANGELOG.md`
- current release notes under `docs/releases/`
- `docs/architecture/dual_backend_pbpk_mcp.md`
- `docs/architecture/mcp_payload_conventions.md`
- `docs/deployment/runtime_patch_flow.md`
- `docs/integration_guides/rxode2_adapter.md`
- `docs/integration_guides/performance_evidence_bundles.md`
- `docs/integration_guides/uncertainty_evidence_bundles.md`
- `docs/hardening_migration_notes.md`
- `docs/github_branch_protection.md`
- `docs/release_readiness.md`
- `docs/pbpk_model_onboarding_checklist.md`
- `benchmarks/regulatory_goldset/regulatory_goldset_summary.md`
- `docs/pbk_reviewer_signoff_checklist.md`
- `docs/post_release_audit_plan.md`
- `.gitignore`

## Post-Push

- create the GitHub release matching the current tag
- use the matching file under `docs/releases/` as the draft release body
- verify the live GitHub `main` ruleset still applies after any repository-level settings change made during release prep
- verify Mermaid rendering on GitHub
- verify relative links in `README.md`
- verify the repository description and topics match the README positioning
- schedule the Day 7 and Day 30 checks from `docs/post_release_audit_plan.md`
