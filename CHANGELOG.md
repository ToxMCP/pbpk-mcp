# Changelog

All notable changes to this project should be documented in this file.

## v0.2.1 - 2026-03-18

### Changed

- restructured the GitHub README into a cleaner public-facing layout with clearer quick start, examples, limitations, and architecture sections
- clarified that `rxode2` is a first-class execution engine alongside `ospsuite`, not only a conversion target
- aligned support, security, package, compose, and environment metadata with the current `ToxMCP/pbpk-mcp` repository

### Fixed

- GitHub Mermaid rendering for the public architecture diagram
- stale `0.1.0` and legacy repository references in package metadata and generated docs

### Notes

- `v0.2.1` is a documentation and release-metadata patch over `v0.2.0`
- runtime behavior and MCP tool semantics are unchanged from the `v0.2.0` feature release

## v0.2.0 - 2026-03-18

### Added

- dual-backend execution model with `ospsuite` for `.pkml` and `rxode2` for MCP-ready `.R`
- filesystem-backed model discovery through `discover_models` and `/mcp/resources/models`
- OECD-oriented `profile` metadata and `validate_simulation_request` preflight assessment
- structured `oecdChecklist` and `oecdChecklistScore` in validation assessments
- sidecar-backed scientific metadata for OSPSuite models
- `rxode2` population simulation support through the dedicated worker image
- stable enhanced MCP response contract with `tool` and `contractVersion`
- GitHub-facing README architecture diagram and limitations documentation

### Changed

- clarified that `rxode2` is a first-class execution backend, not only a conversion target
- flattened async job-status fields for easier client chaining
- separated discoverable model files from loaded simulation sessions
- exposed host API port `8000` in the local Celery deployment
- bumped `SERVICE_VERSION` in `docker-compose.celery.yml` to `0.2.0`

### Fixed

- `.pkml` runtime execution for transfer files with empty `OutputSelections` via bounded observer fallback
- live discovery/index mismatch where custom models like cisplatin were loadable but not discoverable
- validation edge cases around scalar `contextOfUse` values
- async deterministic result retrieval with persisted fallback in `get_results`

### Notes

- Berkeley Madonna `.mmd` remains a conversion source, not a direct runtime format
- many included scientific profiles are still `illustrative-example` or `research-use`, not regulatory-ready
