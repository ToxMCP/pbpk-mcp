# GitHub Publication Checklist

## Before Push

- confirm the README reflects the intended public positioning
- confirm the release version and docs are aligned
- confirm no local runtime artifacts are being committed
- confirm example models included in the repo are intended for public distribution
- confirm no credentials, tokens, or machine-specific paths remain in docs or scripts
- run `python3 -m unittest -v tests/test_oecd_bridge.py`
- run `python3 -m unittest -v tests/test_load_simulation_contract.py`
- run `python3 -m unittest -v tests/test_model_manifest.py`
- run `python3 -m unittest -v tests/test_model_discovery_live_stack.py`
- run `python3 -m unittest -v tests/test_oecd_live_stack.py`
- run `python3 scripts/check_release_metadata.py`
- run `python3 scripts/validate_model_manifests.py --path var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R --path var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml`
- run `python3 scripts/release_readiness_check.py`
- run `python3 scripts/workspace_model_smoke.py`
- run `python3 scripts/workspace_model_smoke.py --include-population`
- if preparing a release, run the repository `Model Smoke` workflow and keep the uploaded smoke JSON artifact with the release evidence
- if preparing a release tag, run the repository `Release Artifacts` workflow and retain the uploaded `sdist`/`wheel` bundle plus `release-artifact-report.json` with the release evidence

## Public Positioning

- describe PBPK MCP as one user-facing MCP with multiple execution backends
- state clearly that `rxode2` is a direct execution backend for PBPK R models
- state clearly that Berkeley Madonna `.mmd` is a conversion source, not a runtime format
- state clearly that `.pksim5` is an export source and should be converted to `.pkml` before runtime use
- state clearly that runnable does not mean scientifically qualified
- state clearly that OECD-oriented metadata supports risk-assessment workflows but does not replace scientific dossier review
- state clearly when the local runtime still relies on source overlays rather than a fully packaged image/runtime boundary

## Files To Review Before Publishing

- `README.md`
- `CHANGELOG.md`
- current release notes under `docs/releases/`
- `docs/architecture/dual_backend_pbpk_mcp.md`
- `docs/deployment/runtime_patch_flow.md`
- `docs/integration_guides/rxode2_adapter.md`
- `docs/integration_guides/performance_evidence_bundles.md`
- `docs/integration_guides/uncertainty_evidence_bundles.md`
- `.gitignore`

## Post-Push

- create the GitHub release matching the current tag
- use the matching file under `docs/releases/` as the draft release body
- verify Mermaid rendering on GitHub
- verify relative links in `README.md`
- verify the repository description and topics match the README positioning
