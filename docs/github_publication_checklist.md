# GitHub Publication Checklist

## Before Push

- confirm the README reflects the intended public positioning
- confirm the release version and docs are aligned
- confirm no local runtime artifacts are being committed
- confirm example models included in the repo are intended for public distribution
- confirm no credentials, tokens, or machine-specific paths remain in docs or scripts
- run `python3 -m unittest -v tests/test_oecd_bridge.py`
- run `python3 scripts/release_readiness_check.py`

## Public Positioning

- describe PBPK MCP as one user-facing MCP with multiple execution backends
- state clearly that `rxode2` is a direct execution backend for PBPK R models
- state clearly that Berkeley Madonna `.mmd` is a conversion source, not a runtime format
- state clearly that runnable does not mean scientifically qualified
- state clearly that OECD-oriented metadata supports risk-assessment workflows but does not replace scientific dossier review

## Files To Review Before Publishing

- `README.md`
- `CHANGELOG.md`
- current release notes under `docs/releases/`
- `docs/architecture/dual_backend_pbpk_mcp.md`
- `docs/integration_guides/rxode2_adapter.md`
- `.gitignore`

## Post-Push

- create the GitHub release matching the current tag
- use the matching file under `docs/releases/` as the draft release body
- verify Mermaid rendering on GitHub
- verify relative links in `README.md`
- verify the repository description and topics match the README positioning
