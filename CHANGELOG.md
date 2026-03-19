# Changelog

All notable changes to this project should be documented in this file.

## Unreleased

- No unreleased changes documented yet.

## v0.2.4 - 2026-03-19

### Added

- `validate_model_manifest` for static pre-load qualification and completeness checks on supported `.pkml` and MCP-ready `.R` models
- explicit `qualificationState` classification in validation responses and OECD dossier exports
- `scripts/validate_model_manifests.py` for release-gating and batch manifest checks across model inventories

### Changed

- extended the OECD-oriented bridge layer to derive reusable qualification-state labels instead of only checklist and readiness summaries
- tightened publication and release-readiness guidance around model manifest completeness and qualification metadata coverage

### Notes

- `v0.2.4` extends the OECD-oriented qualification workflow with reusable qualification states and pre-load manifest validation

## v0.2.3 - 2026-03-19

### Changed

- aligned repository version markers so `README`, package metadata, OpenAPI docs, and compose/runtime surfaces consistently reflect the latest patch release
- moved the post-`v0.2.2` version-alignment follow-up into an explicit release instead of leaving it only on `main`

### Notes

- `v0.2.3` is a release-alignment patch over `v0.2.2`
- it does not change the MCP tool surface or PBPK runtime behavior

## v0.2.2 - 2026-03-19

### Added

- `export_oecd_report` for structured OECD-style dossier export across supported backends
- `modelPerformance`, `parameterProvenance`, and `performanceEvidence` support in the qualification/reporting layer
- `pbpk_parameter_table(...)` and `pbpk_performance_evidence(...)` support in the R model-module contract
- `scripts/release_readiness_check.py` for pre-release validation against the running local stack
- expanded architecture documentation with logical and runtime Mermaid diagrams

### Changed

- made the architecture documentation reflect the current implemented dual-backend design rather than a purely proposed target
- tightened qualification wording so runtime or smoke evidence is not presented as full predictivity evidence
- expanded public limitations documentation around format support, qualification boundaries, and worker/runtime constraints

### Fixed

- preserved sidecar-backed profile provenance cleanly in exported OECD reports
- aligned release documentation with the current OECD reporting and performance-evidence surfaces

## v0.2.1 - 2026-03-19

### Added

- cleaner GitHub-facing README structure with a repaired Mermaid architecture diagram
- refreshed public release notes and publication-oriented documentation surfaces

### Changed

- aligned package, compose, and metadata surfaces to `v0.2.1`
- clarified project positioning around accessibility, OECD orientation, and direct `rxode2` execution

### Notes

- `v0.2.1` was primarily a documentation and release-surface cleanup over `v0.2.0`

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
