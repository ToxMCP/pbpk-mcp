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

Published PBPK-side object schemas:

- `schemas/assessmentContext.v1.json`
- `schemas/pbpkQualificationSummary.v1.json`
- `schemas/uncertaintySummary.v1.json`
- `schemas/uncertaintyHandoff.v1.json`
- `schemas/uncertaintyRegisterReference.v1.json`
- `schemas/internalExposureEstimate.v1.json`
- `schemas/pointOfDepartureReference.v1.json`
- `schemas/berInputBundle.v1.json`

Those schemas intentionally require only the stable core fields. Additive convenience fields remain allowed under `pbpk-mcp.v1`.

The published schema family is also exposed through the live MCP resource surface:

- `/mcp/resources/schemas`
- `/mcp/resources/schemas/{schemaId}`

The machine-readable capability matrix is exposed at:

- `/mcp/resources/capability-matrix`

The machine-readable contract manifest is exposed at:

- `/mcp/resources/contract-manifest`

Those contract resources now expose SHA-256 values for the published artifacts so downstream clients can verify integrity against the contract manifest instead of trusting filenames alone.

JSON-RPC transport note:

- `/mcp` implements MCP `2025-11-25` JSON-RPC by default and accepts legacy `2025-03-26` during the compatibility window
- `initialize` advertises standard `tools: {listChanged: false}` and `resources: {listChanged: false}` capabilities
- `tools/list` exposes `inputSchema`, `outputSchema`, and standard tool annotations for every visible tool
- `tools/call` returns both serialized JSON text content and `structuredContent`
- `resources/list`, `resources/read`, and `resources/templates/list` expose the published contract resources through `pbpk://` URIs
- REST routes under `/mcp/list_tools`, `/mcp/call_tool`, and `/mcp/resources/*` remain compatibility/helper surfaces for scripts and notebooks

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

- MCP trust-bearing tool results
  - `validate_model_manifest`, `discover_models`, `validate_simulation_request`, `run_verification_checks`, and `export_oecd_report` now also expose a top-level `trustSurfaceContract` on `structuredContent`
  - `trustSurfaceContract` is not a second scientific score; it is a client-facing rendering contract that points thin MCP consumers at the nested trust-bearing surfaces they must carry together
  - each listed surface names its `surfacePath`, required adjacent caveat paths, primary block-reason codes, and whether lossy/bare rendering should be refused
  - this keeps future MCP clients aligned with the existing refusal semantics instead of forcing each client to rediscover where the caution, anti-misread, and block-policy fields live

- `load_simulation`
  - returns `simulationId`, `backend`, `metadata`, `capabilities`, `profile`, `validation`, `qualificationState`, and `warnings`
- `discover_models`
  - returns paginated discoverable model entries from disk, including `filePath`, `backend`, `discoveryState`, and `loadedSimulationIds`
  - entries now also include `manifestStatus`, `qualificationState`, and a compact `curationSummary` so reviewers can distinguish fully curated illustrative examples from exploratory or partially declared models without opening each sidecar first
- `validate_model_manifest`
  - returns `filePath`, `backend`, `runtimeFormat`, `manifest`, and `curationSummary`
  - `manifest` includes `manifestStatus`, `qualificationState`, section coverage, and static issues
  - `curationSummary` is a compact reviewer-facing interpretation of the same manifest state, including a review label, NGRA-boundary explicitness, missing sections, a human-readable summary, a descriptive `misreadRiskSummary` block for analyst-facing rendering surfaces, a machine-readable `summaryTransportRisk` block for thin or forwarded views, a normalized `cautionSummary` that separates advisory versus blocking caution handling, an `exportBlockPolicy` that names hard-stop reasons for lossy or decision-leaning reuse, `renderingGuardrails` that explicitly forbid rendering the trust label without adjacent caveats, and an advisory `regulatoryBenchmarkReadiness` block that compares the current dossier to the documentation/reproducibility bar implied by the fetched public-code regulatory gold set
  - `regulatoryBenchmarkReadiness.dimensionStatuses[*]` now also carries `evaluatedFrom`, `observedManifestFields`, `benchmarkExampleIds`, and `recommendedNextArtifacts` so the benchmark comparison is actionable rather than only narrative
- `ingest_external_pbpk_bundle`
  - returns `externalRun`, `ngraObjects`, and `warnings`
  - `externalRun` is a normalized provenance record for imported external PBPK outputs; it does not imply PBPK MCP executed the upstream engine
  - `ngraObjects` carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and `berInputBundle` for imported external data
  - imported NGRA objects now also expose explicit `assessmentBoundary`, `decisionBoundary`, `supports`, and where relevant `requiredExternalInputs`
- `validate_simulation_request`
  - returns `simulationId`, `backend`, `validation`, `profile`, `capabilities`, `ngraObjects`, `qualificationState`, and `warnings`
  - trust-bearing validation responses now also carry `operatorReviewSignoff`, an additive audit-backed summary of the latest recorded operator sign-off state for that simulation/scope, plus `operatorReviewGovernance`, which states explicitly that the sign-off path is descriptive, revocable, non-adjudicative, and not an override workflow
  - `ngraObjects` currently includes PBPK-side typed objects for `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, and `pointOfDepartureReference`
  - these PBPK-side objects now include boundary/support fields so downstream orchestrators can distinguish PBPK execution support from decision-policy ownership
  - `assessmentContext.workflowRole` now states that PBPK MCP is an exposure-led NGRA substrate rather than a full decision engine, including upstream dependencies, downstream outputs, and non-goals
  - `assessmentContext.populationSupport` now states supported population contexts, variability-representation status, and extrapolation policy
  - `pbpkQualificationSummary.evidenceBasis` now provides a compact status view for in vivo support, IVIVE linkage, parameterization basis, and population-variability status
  - `pbpkQualificationSummary.workflowClaimBoundaries` now makes forward-dosimetry support, reverse-dosimetry limits, exposure-led prioritization limits, and the lack of direct regulatory dose derivation explicit
  - `pbpkQualificationSummary.reviewStatus` now carries a compact reviewer-workflow summary, including unresolved-dissent counts, traceability counts, reviewer-attention requirements, optional focus topics, and an additive intervention summary without creating a full override engine
  - `pbpkQualificationSummary.cautionSummary` now normalizes caution entries across evidence-basis limits, detached-summary risk, decision-overclaim boundaries, review dissent, and missing-evidence signals; each caution names `severity`, `handling`, `scope`, and `sourceSurface`
  - `pbpkQualificationSummary.exportBlockPolicy` now carries machine-readable block reasons for detached summaries, bare review badges, direct regulatory-dose overclaim, and other lossy or decision-leaning downstream reuse
  - `uncertaintySummary.semanticCoverage` now provides additive PBPK-side uncertainty semantics, including variability-versus-residual classification, `quantifiedRowCount`, `declaredOnlyRowCount`, and declared-versus-quantified coverage without changing qualification scoring
  - `profile.modelPerformance` may now include normalized `coverage` counters for goodness-of-fit metrics, dataset records, predictive dataset records, and explicit acceptance-criterion coverage
  - `profile.peerReview` may now include normalized `reviewRecords`, `priorRegulatoryUse`, `revisionHistory`, and additive coverage counters such as `reviewRecordCount`, `priorUseCount`, and `revisionEntryCount`
- `run_verification_checks`
  - returns `simulationId`, `backend`, `generatedAt`, `validation`, `profile`, `capabilities`, `qualificationState`, `verification`, and `warnings`
  - trust-bearing verification responses now also carry `operatorReviewSignoff` with the same additive audit-backed semantics as validation and report export, plus `operatorReviewGovernance` so thin clients do not infer hidden override or approval semantics
  - the top-level `trustSurfaceContract` for verification points thin clients at `qualificationState` plus the adjacent `profile.*` boundary fields, `operatorReviewSignoff`, and `operatorReviewGovernance`, because verification responses do not carry the separate `ngraObjects` block used by validation and report export
  - `verification` includes `status`, structured `checks`, smoke-run artifact handles, parameter-unit consistency, structural flow/volume consistency, deterministic integrity/reproducibility results, and a compact `verificationEvidence` snapshot
- `export_oecd_report`
  - returns `simulationId`, `backend`, `generatedAt`, `ngraObjects`, `qualificationState`, and `report`
- `report` includes `qualificationState`, `profile`, `validation`, `oecdChecklist`, `oecdChecklistScore`, additive `oecdCoverage`, `missingEvidence`, `performanceEvidence`, `uncertaintyEvidence`, `verificationEvidence`, `executableVerification`, `platformQualificationEvidence`, and an optional `parameterTable`
  - `report.operatorReviewSignoff` and `report.humanReviewSummary.operatorReviewSignoff` now carry the latest audit-backed operator sign-off summary for report export, including who recorded or revoked it, the stated rationale, and an explicit reminder that sign-off does not confer decision authority
  - `report.operatorReviewGovernance` and `report.humanReviewSummary.operatorReviewGovernance` now make the operating model explicit: sign-off is additive and auditable, but PBPK MCP does not adjudicate scientific truth, override qualification state, or grant regulatory/organizational authority
  - `report.humanReviewSummary` is a compact reviewer-facing block derived from the same machine-readable boundaries already present in `ngraObjects`; it highlights intended workflow, evidence basis, population support, claim boundaries, reviewer-status, normalized `cautionSummary`, summary-transport risk, explicit `exportBlockPolicy`, rendering guardrails, current readiness states, explicit review focus items, and any recorded operator sign-off state
  - `report.exportBlockPolicy` mirrors the same machine-readable refusal semantics at the report root for clients that only inspect top-level report metadata
  - `report.cautionSummary` mirrors the same caution taxonomy at the report root so clients that only inspect top-level metadata still see advisory versus blocking caution semantics
  - `report.misreadRiskSummary` is a mandatory anti-misread section placed next to the primary report summary; it states the main over-interpretation risks in plain language, includes machine-readable risk statements, and names the reviewer checks that still need human judgement, including detached-summary/forwarding risk
  - `report.ngraObjects` is a self-contained PBPK-side NGRA object block; it currently carries `assessmentContext`, `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and a thin `berInputBundle`
  - `berInputBundle` is deliberately BER-ready only: it does not calculate BER or make a decision recommendation
  - `berInputBundle` remains incomplete until the caller supplies an external `podRef` and the PBPK side has a resolved internal exposure target/metric; when both are present it can become `ready-for-external-ber-calculation`
  - `pointOfDepartureReference` is a typed external PoD handoff object only; it does not mean PBPK MCP validated PoD suitability or owns PoD interpretation
  - `assessmentContext.workflowRole`, `assessmentContext.populationSupport`, `pbpkQualificationSummary.evidenceBasis`, and `pbpkQualificationSummary.workflowClaimBoundaries` are descriptive boundary fields; they do not create a second hidden qualification score
  - `pbpkQualificationSummary`, `uncertaintySummary`, `uncertaintyHandoff`, `internalExposureEstimate`, `uncertaintyRegisterReference`, `pointOfDepartureReference`, and `berInputBundle` now expose machine-readable `assessmentBoundary` / `decisionBoundary` fields plus support flags; `berInputBundle` also names the external decision owner explicitly
  - `uncertaintyHandoff` is a separate PBPK-to-cross-domain uncertainty handoff object; it references the PBPK qualification, PBPK uncertainty, internal exposure, and optional PoD-reference objects, but leaves uncertainty synthesis and decision ownership with the external orchestrator
  - `uncertaintySummary.semanticCoverage` and the corresponding `uncertaintyHandoff.supports` flags make the PBPK-side uncertainty boundary more explicit by distinguishing quantified variability, structured-but-non-quantified sensitivity, and declared residual uncertainty
  - `uncertaintySummary.semanticCoverage.variabilityQuantificationStatus = quantified` is only emitted when `variability-propagation` evidence rows actually carry quantitative outputs such as `value`, `lowerBound`, `upperBound`, `mean`, or `sd`
  - `uncertaintyRegisterReference` is a typed external reference only; it does not mean PBPK MCP owns the cross-domain uncertainty register or the synthesis logic built on top of it
  - `oecdCoverage` is a descriptive mapping layer aligned to OECD PBK Guidance Tables 3.1 and 3.2; it is explicitly non-scoring (`affectsChecklistScore = false`, `affectsQualificationState = false`) and exists to show dossier coverage gaps without creating a second hidden qualification score
  - `humanReviewSummary` is also descriptive only; it does not alter `qualificationState`, `oecdChecklistScore`, or decision ownership
  - `cautionSummary` is descriptive only too; it normalizes caution semantics and handling across surfaces, but it does not introduce a second hidden qualification score or override engine
  - `exportBlockPolicy` and `renderingGuardrails` are descriptive policy surfaces for clients and future frontends; they do not create a hidden approval engine, but they do state when a thin or decision-leaning rendering should be refused
  - `operatorReviewSignoff` is descriptive only as well; it records who acknowledged, approved for bounded use, rejected, or revoked a trust-bearing surface, but it does not create a hidden authorization layer
  - `operatorReviewGovernance` is descriptive only too; it exists so clients can render the absence of override/adjudication authority explicitly instead of inferring it from prose
  - `misreadRiskSummary` is descriptive only as well; it adds friction against common overclaims, but it does not block export or change qualification state on its own
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
