# MCP Payload Conventions

This workspace now uses a small stable response contract for the OECD-enhanced MCP tools that are patched in-repo.

Current contract version:

- `pbpk-mcp.v1`

Applied tools:

- `discover_models`
- `ingest_external_pbpk_bundle`
- `validate_model_manifest`
- `load_simulation`
- `validate_simulation_request`
- `run_verification_checks`
- `export_oecd_report`
- `get_job_status`
- `get_results`

## Stable Top-Level Fields

All enhanced tool responses now include:

- `tool`
  - exact MCP tool name that produced the payload
- `contractVersion`
  - stable payload contract version for client-side branching

Model-bound enhanced responses also flatten backend information when available:

- `backend`
  - `ospsuite` or `rxode2`

## Tool-Specific Notes

- `load_simulation`
  - returns `simulationId`, `backend`, `metadata`, `capabilities`, `profile`, `validation`, `qualificationState`, and `warnings`
- `discover_models`
  - returns paginated discoverable model entries from disk, including `filePath`, `backend`, `discoveryState`, and `loadedSimulationIds`
- `validate_model_manifest`
  - returns `filePath`, `backend`, `runtimeFormat`, and `manifest`
  - `manifest` includes `manifestStatus`, `qualificationState`, section coverage, and static issues
- `ingest_external_pbpk_bundle`
  - returns `externalRun`, `ngraObjects`, and `warnings`
  - `externalRun` is a normalized provenance record for imported external PBPK outputs; it does not imply PBPK MCP executed the upstream engine
  - `ngraObjects` carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and `berInputBundle` for imported external data
  - imported NGRA objects now also expose explicit `assessmentBoundary`, `decisionBoundary`, `supports`, and where relevant `requiredExternalInputs`
- `validate_simulation_request`
  - returns `simulationId`, `backend`, `validation`, `profile`, `capabilities`, `ngraObjects`, `qualificationState`, and `warnings`
  - `ngraObjects` currently includes PBPK-side typed objects for `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, and `pointOfDepartureReference`
  - these PBPK-side objects now include boundary/support fields so downstream orchestrators can distinguish PBPK execution support from decision-policy ownership
  - `uncertaintySummary.semanticCoverage` now provides additive PBPK-side uncertainty semantics, including variability-versus-residual classification, `quantifiedRowCount`, `declaredOnlyRowCount`, and declared-versus-quantified coverage without changing qualification scoring
  - `profile.modelPerformance` may now include normalized `coverage` counters for goodness-of-fit metrics, dataset records, predictive dataset records, and explicit acceptance-criterion coverage
  - `profile.peerReview` may now include normalized `reviewRecords`, `priorRegulatoryUse`, `revisionHistory`, and additive coverage counters such as `reviewRecordCount`, `priorUseCount`, and `revisionEntryCount`
- `run_verification_checks`
  - returns `simulationId`, `backend`, `generatedAt`, `validation`, `profile`, `capabilities`, `qualificationState`, `verification`, and `warnings`
  - `verification` includes `status`, structured `checks`, smoke-run artifact handles, parameter-unit consistency, structural flow/volume consistency, deterministic integrity/reproducibility results, and a compact `verificationEvidence` snapshot
- `export_oecd_report`
  - returns `simulationId`, `backend`, `generatedAt`, `ngraObjects`, `qualificationState`, and `report`
- `report` includes `qualificationState`, `profile`, `validation`, `oecdChecklist`, `oecdChecklistScore`, additive `oecdCoverage`, `missingEvidence`, `performanceEvidence`, `uncertaintyEvidence`, `verificationEvidence`, `executableVerification`, `platformQualificationEvidence`, and an optional `parameterTable`
  - `report.ngraObjects` is a self-contained PBPK-side NGRA object block; it currently carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and a thin `berInputBundle`
  - `berInputBundle` is deliberately BER-ready only: it does not calculate BER or make a decision recommendation
  - `berInputBundle` remains incomplete until the caller supplies an external `podRef` and the PBPK side has a resolved internal exposure target/metric; when both are present it can become `ready-for-external-ber-calculation`
  - `pointOfDepartureReference` is a typed external PoD handoff object only; it does not mean PBPK MCP validated PoD suitability or owns PoD interpretation
  - `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and `berInputBundle` now expose machine-readable `assessmentBoundary` / `decisionBoundary` fields plus support flags; `berInputBundle` also names the external decision owner explicitly
  - `uncertaintyHandoff` is a separate PBPK-to-cross-domain uncertainty handoff object; it references the PBPK qualification, PBPK uncertainty, internal exposure, and optional PoD-reference objects, but leaves uncertainty synthesis and decision ownership with the external orchestrator
  - `uncertaintySummary.semanticCoverage` and the corresponding `uncertaintyHandoff.supports` flags make the PBPK-side uncertainty boundary more explicit by distinguishing quantified variability, structured-but-non-quantified sensitivity, and declared residual uncertainty
  - `uncertaintySummary.semanticCoverage.variabilityQuantificationStatus = quantified` is only emitted when `variability-propagation` evidence rows actually carry quantitative outputs such as `value`, `lowerBound`, `upperBound`, `mean`, or `sd`
  - `uncertaintyRegisterReference` is a typed external reference only; it does not mean PBPK MCP owns the cross-domain uncertainty register or the synthesis logic built on top of it
  - `oecdCoverage` is a descriptive mapping layer aligned to OECD PBK Guidance Tables 3.1 and 3.2; it is explicitly non-scoring (`affectsChecklistScore = false`, `affectsQualificationState = false`) and exists to show dossier coverage gaps without creating a second hidden qualification score
  - `performanceEvidence` includes row-level classification plus summary fields such as `strongestEvidenceClass`, `qualificationBoundary`, and flags indicating whether observed-versus-predicted, predictive-dataset, or external-qualification evidence is actually bundled
  - `performanceEvidence.traceability` summarizes dataset-record and acceptance-criterion coverage derived from the current `modelPerformance` profile, exported evidence rows, and any companion `profileSupplement`
  - `performanceEvidence.traceabilityConsistency` reports how many bundled evidence rows actually match the declared datasets, target outputs, and acceptance criteria; mismatches are surfaced as warnings instead of being silently treated as traceable
  - `performanceEvidence.predictiveDatasetSummary` summarizes bundled dataset names, target outputs, metrics, and acceptance-criterion counts so predictive-supporting evidence is easier to audit without inferring everything from raw rows
  - `performanceEvidence` may be merged from a model hook, `profile.modelPerformance.evidence`, and an optional companion bundle such as `model.performance.json`; companion bundles may also include a traceability-only `profileSupplement`, and exported metadata includes `source`, `sources`, and `sidecarPath` when relevant
  - `uncertaintyEvidence` may be merged from a model hook, `profile.uncertainty.evidence`, and an optional companion bundle such as `model.uncertainty.json`; exported metadata includes `source`, `sources`, and `sidecarPath` when relevant
  - `parameterTable` may be merged from `pbpk_parameter_table(...)`, the runtime parameter catalog or enumeration, and an optional companion bundle such as `model.parameters.json`; exported metadata now includes `source`, `sources`, `sidecarPath`, `bundleMetadata`, `issues`, and `coverage`
  - `parameterTable.coverage` summarizes row counts plus how many rows carry units, sources, source citations, distributions/statistics, experimental conditions, and rationale or motivation
  - `parameterTable` companion-bundle metadata is descriptive only; it does not affect `oecdChecklistScore` or `qualificationState`
  - `peerReviewAndPriorUse` in the checklist now distinguishes status, structured review records, prior-use traceability, revision status, and revision-history entries instead of relying only on a single review status token
  - `executableVerification` is a stored snapshot from the latest `run_verification_checks` call for that loaded simulation; report export does not implicitly rerun verification
- `get_job_status`
  - returns top-level `jobId`, `status`, `resultId`, and `resultHandle.resultsId`
  - still includes nested `job` for backward compatibility
- `get_results`
  - returns `resultsId`, `simulationId`, `backend`, `generatedAt`, `metadata`, and `series`

## Compatibility Rule

New convenience fields may be added, but existing stable fields in `pbpk-mcp.v1` should not be removed or renamed without bumping `contractVersion`.
