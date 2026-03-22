# Changelog

All notable changes to this project should be documented in this file.

## Unreleased

### Changed

- `docker-compose.celery.yml` now runs the packaged local runtime by default, while `docker-compose.overlay.yml` and `scripts/deploy_source_overlay_stack.sh` provide the explicit source-overlay maintainer path
- `scripts/runtime_src_overlay.pth` is now conditional on `PBPK_ENABLE_SRC_OVERLAY`, so the worker image can run in either packaged or overlay mode without changing the public contract
- deployment docs now describe the packaged-default local runtime with an opt-in overlay profile, rather than treating the source overlay as the only local mode

## v0.4.0 - 2026-03-22

### Added

- published versioned JSON Schemas plus example payloads for the PBPK-side NGRA object family under `schemas/` and `schemas/examples/`
- a dedicated capability matrix under `docs/architecture/capability_matrix.md` and `docs/architecture/capability_matrix.json`, plus matching live MCP resources for schemas, the capability matrix, and the machine-readable contract manifest
- a generated `mcp_bridge.contract` packaged fallback plus contract integrity hashes on the live MCP resources so packaged installs and running APIs can both prove which `pbpk-mcp.v1` artifacts they serve
- hardened packaging and release gates including `check_runtime_contract_env.py`, `check_installed_package_contract.py`, `check_distribution_artifacts.py`, `check_release_metadata.py`, and the tag-oriented `release-artifacts.yml` workflow
- a hardened deployment overlay in `docker-compose.hardened.yml` plus `scripts/deploy_hardened_stack.sh` so the local stack can be exercised with explicit auth settings and anonymous access disabled
- direct release-artifact evidence reporting, including retained distribution hashes linked back to the published contract manifest

### Changed

- package metadata now describes PBPK MCP as a dual-backend PBPK qualification, verification, and reporting server rather than an OSPSuite-only bridge
- the generic MCP runtime surface now lives in packaged `src/`, including shared route/resource logic, the tool registry, workflow tools, the top-level `mcp` namespace, and the generic adapter/runtime boundary
- the published schema, capability-matrix, and contract-manifest resources now treat packaged `mcp_bridge.contract` artifacts as authoritative and expose integrity hashes derived from the published artifact inventory
- the worker image now bakes the baseline runtime assets directly, while the local stack overlays workspace `src/`, `scripts/`, and `var/` through bind mounts plus `scripts/runtime_src_overlay.pth`
- local deployment and architecture docs now describe the runtime as a packaged `src/` implementation plus local source overlays rather than a tracked patch implementation layer
- distribution and staged-source checks now ignore heavyweight local runtime directories, build outputs, virtual environments, and scratch state so maintainer-local workspace clutter does not poison release validation

### Removed

- the tracked patch implementation layer for generic Python contract code
- the last live patch-copy/install step, including the obsolete runtime patch manifest and installer scripts from the local deployment flow
- the dependency on copied contract JSON under `/app/var/contract` for the generic live MCP contract resources

### Notes

- `v0.4.0` formalizes the published `pbpk-mcp.v1` contract and significantly reduces patch-first debt without changing the public PBPK workflow shape or moving BER/assessment decision logic into PBPK MCP
- the local source-overlay stack remains a development/operator path; a fully packaged default runtime boundary is still the longer-term destination

## v0.3.5 - 2026-03-21

### Added

- additive `uncertaintyHandoff.v1` PBPK-side NGRA object in both native and external-normalization flows, so downstream orchestrators can consume a typed PBPK uncertainty handoff without giving PBPK MCP ownership of cross-domain uncertainty synthesis
- additive `uncertaintyRegisterReference.v1` handoff object for optional external uncertainty-register provenance in both native and external-normalization flows
- companion performance bundles can now add a traceability-only `profileSupplement` so predictive dataset records, acceptance criteria, and target outputs can be documented without writing new bridge code
- additive `uncertaintySummary.semanticCoverage` semantics in both native and external-normalization flows, so PBPK-side variability, sensitivity, and residual uncertainty can be distinguished as quantified, declared-only, or still missing without inferring that from raw evidence rows
- additive `performanceEvidence.traceabilityConsistency` reporting, so bundled predictive evidence can be checked against declared datasets, target outputs, and acceptance criteria instead of only being counted
- additive `uncertaintySummary.semanticCoverage` counters for `quantifiedRowCount` and `declaredOnlyRowCount`, plus stricter quantitative-signal handling for `variability-propagation` rows
- `scripts/wait_for_runtime_ready.py` plus deploy-path readiness stabilization, so local patch-first redeploys now wait for stable `/health` and `/mcp/list_tools` responses before returning

### Changed

- release-readiness and live-stack tests now assert the new uncertainty handoff boundary alongside BER and PoD handoff semantics
- removed product-specific downstream-orchestrator references from the public documentation in favor of generic integration language
- `performanceEvidence` now reports a `predictiveDatasetSummary` and merges companion `profileSupplement` content into traceability counts without changing qualification scoring
- `uncertaintyHandoff.supports` now exposes whether typed uncertainty semantics are attached and whether PBPK-side variability, sensitivity, or residual uncertainty are actually quantified
- uncertainty bundle validation now warns when `variability-propagation` rows declare propagation scope without exporting any quantitative outputs
- performance bundle validation now warns when row-level dataset, target-output, or acceptance-criterion fields do not match the declared traceability supplement

## v0.3.4 - 2026-03-21

### Changed

- tightened the PBPK-side NGRA handoff objects so `pbpkQualificationSummary`, `uncertaintySummary`, `internalExposureEstimate`, and `berInputBundle` now expose explicit boundary/support metadata for downstream orchestration
- made BER handoff ownership more explicit by identifying external decision ownership and required external inputs in both native and imported PBPK-side bundles
- split external PoD metadata into a typed `pointOfDepartureReference` handoff object so PoD provenance is explicit without moving PoD interpretation into PBPK MCP
- `export_oecd_report` now adds a descriptive `oecdCoverage` block aligned to OECD PBK Guidance Tables 3.1 and 3.2, without changing `oecdChecklistScore` or `qualificationState`
- parameter tables can now be enriched generically through companion bundles such as `model.parameters.json`, with row-level coverage reporting for sources, citations, distributions, study conditions, and rationale in both static manifests and OECD dossier export
- `peerReview` metadata are now normalized into structured review-record, prior-use, and revision-history coverage rather than being treated only as a free-text status flag
- `modelPerformance` metadata now normalize structured dataset records and acceptance-criterion coverage so predictive-support traceability is not reduced to a single status field

### Added

- generic parameter-table companion bundle support and starter documentation/template for `.pkml` and MCP-ready `.R` models

### Fixed

- redeployed live-stack parameter-table coverage so the running `export_oecd_report` contract now matches the enriched local bridge payload

### Notes

- this increment strengthens OECD-style parameter provenance/reporting completeness without changing qualification scoring or NGRA decision ownership

## v0.3.3 - 2026-03-21

### Added

- `ingest_external_pbpk_bundle` for normalization-only import of external PBPK run outputs and qualification metadata into PBPK MCP's typed NGRA-side object surface
- additive `ngraObjects` in `validate_simulation_request` and `export_oecd_report`, including `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, and `internalExposureEstimate`
- dossier-level `berInputBundle` handoff metadata that becomes `ready-for-external-ber-calculation` only when a real internal exposure metric and external `podRef` are both present
- dedicated unit coverage for external PBPK bundle normalization in `tests/test_external_pbpk_bundle.py`

### Changed

- extended the patch-first public contract so external PBPK outputs can be normalized into the same typed PBPK-side objects used by native `.pkml` and MCP-ready `.R` workflows
- updated release-readiness checks to assert the `ingest_external_pbpk_bundle` tool and its BER-handoff status in the live API
- updated `make runtime-contract-test` so the public contract gate includes the external-ingestion unit test
- aligned repository and compose/runtime version markers to `0.3.3`

### Notes

- `v0.3.3` extends `v0.3.2` with NGRA-ready PBPK object export and normalization-only external PBPK ingestion
- it does not execute commercial PBPK engines, parse proprietary project files, calculate BER, or move decision policy into PBPK MCP

## v0.3.2 - 2026-03-20

### Fixed

- removed the compose-level `PYTHONPATH=/app/src` override from the local API and worker deployment so the patch-first runtime no longer shadows the installed `mcp_bridge` package with an incomplete mounted `src/` tree
- restored clean startup for `mcp_bridge.app:create_app` and `mcp_bridge.services.celery_app.celery_app` in the local Docker deployment

### Changed

- aligned the local deployment path with the actual patch-first operating model: patched installed package first, mounted `src/` only as reference material instead of import precedence

### Notes

- `v0.3.2` is a deployment-hotfix release over `v0.3.1`
- it does not change the public MCP tool workflow or the OECD evidence model; it fixes local runtime startup and release hygiene
## v0.3.1 - 2026-03-20

### Added

- structured `uncertaintyEvidence` and `verificationEvidence` export in the OECD report path
- structured `platformQualificationEvidence` export in the OECD report path
- optional `pbpk_uncertainty_evidence(...)`, `pbpk_verification_evidence(...)`, and `pbpk_platform_qualification_evidence(...)` hooks for MCP-ready `rxode2` models
- `scripts/workspace_model_smoke.py` for discovery-first, catalog-wide runtime smoke checks across the live API
- a converged `run_population_simulation` patch tool that uses loaded `simulationId` sessions and treats `modelPath` as legacy-only compatibility
- `run_verification_checks` for executable smoke-oriented verification across loaded `ospsuite` and `rxode2` models
- deterministic result-integrity and repeat-run reproducibility checks in the executable verification path
- optional `pbpk_run_verification_checks(...)` hooks for model-specific executable qualification checks such as mass balance and solver-stability heuristics
- stored `executableVerification` snapshots in `export_oecd_report` so OECD dossiers can carry the latest executed verification results without implicitly rerunning them
- parameter-catalog and parameter-table snapshots are now passed into `pbpk_run_verification_checks(...)` so model-specific runtime checks can validate exposed units and structural coverage
- executable structural physiology checks for systemic flow distribution and renal volume partition consistency in the cisplatin example model
- bounded local sensitivity evidence for the cisplatin example, exported through `uncertaintyEvidence` with current-parameter context rather than a placeholder sensitivity gap
- bounded variability-propagation evidence for the cisplatin example, exported through `uncertaintyEvidence` as a compact internal-exposure distribution summary
- explicit performance-evidence classification and qualification-boundary summaries in `export_oecd_report`, so runtime smoke/internal evidence is separated from predictive and external qualification evidence
- generic companion performance-evidence bundles for `.pkml` and MCP-ready `.R` models via files such as `model.performance.json`
- reusable starter template for companion performance-evidence bundles at `examples/performance_evidence_bundle.template.json`
- generic companion uncertainty-evidence bundles for `.pkml` and MCP-ready `.R` models via files such as `model.uncertainty.json`
- reusable starter template for companion uncertainty-evidence bundles at `examples/uncertainty_evidence_bundle.template.json`

### Changed

- static manifest inspection now detects uncertainty, verification, and platform-qualification evidence hooks on R models
- README and integration guides now document the richer OECD evidence export surface
- live regression checks now assert the `run_population_simulation` contract no longer requires `modelPath`
- maintainer documentation now treats workspace-model smoke as a first-class verification step for release hygiene
- release-readiness checks now exercise the executable verification surface in addition to validation, execution, and OECD report export
- executable verification now goes beyond smoke-only checks by asserting deterministic result integrity and repeat-run reproducibility
- OECD checklist/report generation now separates software-platform qualification evidence from implementation verification evidence
- the cisplatin example now contributes executable mass-balance and solver-stability checks through the runtime verification hook
- OECD report export now carries stored executable verification snapshots separately from static `verificationEvidence`
- the cisplatin example now contributes executable parameter-unit consistency checks through the runtime verification hook
- the cisplatin example now contributes executable systemic-flow and renal-volume consistency checks through the runtime verification hook
- bridge evidence hooks now receive the loaded runtime parameter context and parameter-table snapshot so uncertainty/performance evidence can reflect the actual loaded model state
- cisplatin runtime smoke evidence is now explicitly labeled as internal operational evidence rather than implied predictive support
- static manifest inspection now treats a companion performance-evidence bundle as a valid alternative to a dedicated `pbpk_performance_evidence(...)` hook for `R` models
- companion performance-evidence bundles can now expose bundle-level metadata, and that metadata is surfaced through static manifest inspection and OECD report export
- malformed performance-evidence rows are now surfaced as warnings during static manifest inspection and OECD report export instead of being silently normalized
- static manifest inspection now treats a companion uncertainty-evidence bundle as a valid alternative to a dedicated `pbpk_uncertainty_evidence(...)` hook for `R` models
- companion uncertainty-evidence bundles can now expose bundle-level metadata, and that metadata is surfaced through static manifest inspection and OECD report export
- malformed uncertainty-evidence rows are now surfaced as warnings during static manifest inspection and OECD report export instead of being silently normalized

### Notes

- `v0.3.1` extends the `v0.3.0` contract-convergence line with executable verification and generic qualification-evidence bundle support
- the public MCP workflow is unchanged; this release strengthens qualification evidence, validation, and release hygiene around that workflow

## v0.3.0 - 2026-03-20

### Added

- shared runtime patch manifest and installer so the Docker image build and hot-patch workflow use the same file map
- release-readiness checks for tool-catalog exposure, discovery/resource parity, and explicit `.pksim5` rejection guidance
- load-policy contract tests covering conversion-only format messaging

### Changed

- made the patch-first runtime layer explicit as the canonical implementation surface for this convergence stage
- updated `scripts/deploy_rxode2_stack.sh` to recreate the stack and immediately reapply the current workspace patch set
- changed `scripts/apply_rxode2_patch.py` to patch both API and worker containers by default
- tightened direct `.pksim5` and `.mmd` rejection messages so conversion guidance is explicit and consistent with the published architecture

### Notes

- `v0.3.0` is the contract-convergence milestone for the current patch-first PBPK MCP runtime
- packaging migration into a pure `src/` implementation is intentionally deferred to a later stage

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
