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
  - `ngraObjects` carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `internalExposureEstimate`, and `berInputBundle` for imported external data
- `validate_simulation_request`
  - returns `simulationId`, `backend`, `validation`, `profile`, `capabilities`, `ngraObjects`, `qualificationState`, and `warnings`
  - `ngraObjects` currently includes PBPK-side typed objects for `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, and `internalExposureEstimate`
- `run_verification_checks`
  - returns `simulationId`, `backend`, `generatedAt`, `validation`, `profile`, `capabilities`, `qualificationState`, `verification`, and `warnings`
  - `verification` includes `status`, structured `checks`, smoke-run artifact handles, parameter-unit consistency, structural flow/volume consistency, deterministic integrity/reproducibility results, and a compact `verificationEvidence` snapshot
- `export_oecd_report`
  - returns `simulationId`, `backend`, `generatedAt`, `ngraObjects`, `qualificationState`, and `report`
- `report` includes `qualificationState`, `profile`, `validation`, `oecdChecklist`, `oecdChecklistScore`, `missingEvidence`, `performanceEvidence`, `uncertaintyEvidence`, `verificationEvidence`, `executableVerification`, `platformQualificationEvidence`, and an optional `parameterTable`
  - `report.ngraObjects` is a self-contained PBPK-side NGRA object block; it currently carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `internalExposureEstimate`, and a thin `berInputBundle`
  - `berInputBundle` is deliberately BER-ready only: it does not calculate BER or make a decision recommendation
  - `berInputBundle` remains incomplete until the caller supplies an external `podRef` and the PBPK side has a resolved internal exposure target/metric; when both are present it can become `ready-for-external-ber-calculation`
  - `performanceEvidence` includes row-level classification plus summary fields such as `strongestEvidenceClass`, `qualificationBoundary`, and flags indicating whether observed-versus-predicted, predictive-dataset, or external-qualification evidence is actually bundled
  - `performanceEvidence` may be merged from a model hook, `profile.modelPerformance.evidence`, and an optional companion bundle such as `model.performance.json`; exported metadata includes `source`, `sources`, and `sidecarPath` when relevant
  - `uncertaintyEvidence` may be merged from a model hook, `profile.uncertainty.evidence`, and an optional companion bundle such as `model.uncertainty.json`; exported metadata includes `source`, `sources`, and `sidecarPath` when relevant
  - `executableVerification` is a stored snapshot from the latest `run_verification_checks` call for that loaded simulation; report export does not implicitly rerun verification
- `get_job_status`
  - returns top-level `jobId`, `status`, `resultId`, and `resultHandle.resultsId`
  - still includes nested `job` for backward compatibility
- `get_results`
  - returns `resultsId`, `simulationId`, `backend`, `generatedAt`, `metadata`, and `series`

## Compatibility Rule

New convenience fields may be added, but existing stable fields in `pbpk-mcp.v1` should not be removed or renamed without bumping `contractVersion`.
