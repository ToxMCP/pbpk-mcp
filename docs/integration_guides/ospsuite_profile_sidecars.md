# OSPSuite Profile Sidecars

## Purpose

OSPSuite transfer files (`.pkml`) do not carry the richer OECD-style scientific profile metadata that the MCP now exposes for `rxode2` models.

To attach project-specific scientific metadata to a `.pkml` model without modifying the transfer file itself, the bridge supports optional JSON sidecar files.

## Supported Sidecar Names

For a model path such as:

```text
/app/var/models/example/Pregnant_simulation_PKSim.pkml
```

the bridge checks, in order:

```text
/app/var/models/example/Pregnant_simulation_PKSim.profile.json
/app/var/models/example/Pregnant_simulation_PKSim.pbpk.json
/app/var/models/example/Pregnant_simulation_PKSim.pkml.profile.json
```

The first existing file is used.

## Payload Shape

The sidecar may be either:

- a direct profile object, or
- an object with a top-level `profile` field

Supported sections mirror the current MCP scientific profile structure:

- `contextOfUse`
- `applicabilityDomain`
- `modelPerformance`
- `parameterProvenance`
- `uncertainty`
- `implementationVerification`
- `peerReview`

Inside `peerReview`, richer traceability can now be declared with fields such as:

- `reviewRecords`
- `priorRegulatoryUse`
- `revisionStatus`
- `revisionHistory`

The bridge normalizes those fields and reports additive coverage counters in the merged profile so OECD dossier exports can distinguish peer review, prior use, and revision traceability more explicitly.

For richer performance reporting, `modelPerformance` may also include structured fields such as:

- `goodnessOfFit.metrics`
- `goodnessOfFit.datasets`
- `goodnessOfFit.datasetRecords`
- `predictiveChecks.datasets`
- `predictiveChecks.datasetRecords`
- `goodnessOfFit.acceptanceCriteria`
- `predictiveChecks.acceptanceCriteria`
- `evidence`

When these richer fields are present, the bridge exposes additive coverage counts in the normalized profile and performance-report output so predictive-support traceability is more explicit.

If you prefer to keep quantitative evidence separate from the scientific profile, PBPK MCP also supports dedicated companion bundles such as:

- `model.performance.json`
- `model.performance-evidence.json`

Those bundles work for both `.pkml` and MCP-ready `.R` models and are documented in [performance_evidence_bundles.md](/Volumes/Storage/topotox_offload/20260220_space_relief/manual_offload/PBPK_MCP/docs/integration_guides/performance_evidence_bundles.md).

The same companion-bundle pattern is also available for uncertainty/sensitivity content via files such as:

- `model.uncertainty.json`
- `model.uncertainty-evidence.json`

Those bundles are documented in [uncertainty_evidence_bundles.md](/Volumes/Storage/topotox_offload/20260220_space_relief/manual_offload/PBPK_MCP/docs/integration_guides/uncertainty_evidence_bundles.md).

The same companion-bundle pattern is now available for richer parameter tables via files such as:

- `model.parameters.json`
- `model.parameter-table.json`

Those bundles are documented in [parameter_table_bundles.md](/Volumes/Storage/topotox_offload/20260220_space_relief/manual_offload/PBPK_MCP/docs/integration_guides/parameter_table_bundles.md).

For richer uncertainty and verification reporting, the sidecar may also include structured evidence rows such as:

- `uncertainty.evidence`
- `uncertainty.evidenceRows`
- `implementationVerification.evidence`
- `implementationVerification.evidenceRows`

Unspecified sections fall back to the bridge defaults for OSPSuite `.pkml` models.

## Behavior

When a sidecar is found:

- `validate_model_manifest` can inspect the sidecar statically before the model is loaded
- `load_simulation` returns the merged `profile`
- `capabilities.scientificProfile` becomes `true`
- `capabilities.applicabilityDomain` mirrors the merged profile domain
- `profile.profileSource.type` is set to `sidecar`
- `validate_simulation_request` can compare a requested context of use or domain hint against the declared sidecar metadata before execution
- `export_oecd_report` can bundle the merged sidecar profile with a live validation assessment and runtime-derived parameter table
- `qualificationState` is derived from the declared qualification level plus dossier-section coverage
- `validation.assessment.oecdChecklist` reports per-dimension OECD-style metadata coverage
- `validation.assessment.oecdChecklistScore` summarizes that coverage numerically

When a `.pkml` file declares an empty `OutputSelections` block:

- the bridge keeps the declared scientific/profile metadata unchanged
- `load_simulation` emits a warning explaining that runtime outputs were auto-seeded
- `capabilities.outputSelectionMode` is set to `observer-fallback`
- a bounded observer-based output set is selected so deterministic execution can proceed

When no sidecar is found:

- `validate_model_manifest` reports the transfer file as `exploratory`
- the bridge returns the OSPSuite default profile
- `capabilities.scientificProfile` remains `false`
- `profile.profileSource.type` is `bridge-default`

## Example

This workspace includes an example sidecar for:

```text
var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml
```

at:

```text
var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.profile.json
```

That example is intentionally conservative and now carries model-specific scope statements, such as route, species, or example-model status where those can be inferred safely from the transfer file and filename. It still does not imply a formal qualification package.

## Curated Workspace Set

The current workspace now ships sidecars for the curated profile/example models:

- `var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml`
- `var/models/esqlabs/PBPK-for-cross-species-extrapolation/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rat.pkml`
- `var/models/esqlabs/TissueTMDD/repeated dose model.pkml`
- `var/models/esqlabs/esqlabsR/simple.pkml`

These sidecars are intentionally conservative, but they are no longer generic `demo-only` placeholders. They now distinguish illustrative scientific examples from pure integration fixtures and encode the strongest scope statement that can be supported from the workspace artifacts alone. They still do not claim formal scientific qualification.
