# Uncertainty Evidence Bundles

## Purpose

PBPK MCP should let model authors attach structured uncertainty and sensitivity evidence without forcing them to implement a custom `pbpk_uncertainty_evidence(...)` hook first.

To keep the MCP reusable across different PBPK models, the runtime now supports optional companion JSON bundles for `uncertaintyEvidence`. These bundles are intentionally conservative: they let a researcher attach bounded sensitivity, variability-propagation, or residual-uncertainty rows next to a model file without changing bridge code.

## Supported Companion Names

For either:

```text
/app/var/models/example/model.pkml
/app/var/models/example/model.R
```

the bridge and static manifest inspection now check, in order:

```text
/app/var/models/example/model.uncertainty.json
/app/var/models/example/model.uncertainty-evidence.json
/app/var/models/example/model.pkml.uncertainty.json
/app/var/models/example/model.pkml.uncertainty-evidence.json
/app/var/models/example/model.R.uncertainty.json
/app/var/models/example/model.R.uncertainty-evidence.json
```

## Payload Shape

The companion bundle may be:

- an object with top-level `rows`
- an object with `uncertaintyEvidence.rows`
- a top-level array of evidence rows

Each row can use fields already recognized by `uncertaintyEvidence`, for example:

- `id`
- `kind`
- `status`
- `summary`
- `method`
- `metric`
- `targetOutput`
- `variedParameters`
- `lowerBound`
- `upperBound`
- `value`
- `notes`

Optional bundle-level metadata is also supported:

- `metadata.bundleVersion`
- `metadata.summary`
- `metadata.evidenceScope`
- `metadata.curator`
- `metadata.createdAt`
- `metadata.notes`

## Runtime Behavior

When `export_oecd_report` runs, PBPK MCP merges uncertainty evidence from:

1. `pbpk_uncertainty_evidence(...)`
2. `profile.uncertainty.evidence` / `evidenceRows`
3. the companion uncertainty bundle

If companion bundle metadata is present, `export_oecd_report` also returns it as `uncertaintyEvidence.bundleMetadata`.

## Static Manifest Behavior

`validate_model_manifest` now detects companion uncertainty bundles statically.

For MCP-ready `R` models:

- an uncertainty bundle can satisfy the uncertainty-evidence requirement even if `pbpk_uncertainty_evidence(...)` is not declared
- the manifest reports `hooks.uncertaintyEvidenceSidecar = true`
- the manifest exposes `supplementalEvidence.uncertaintyEvidenceSidecarPath`
- the manifest exposes `supplementalEvidence.uncertaintyEvidenceRowCount`
- the manifest exposes `supplementalEvidence.uncertaintyEvidenceBundleMetadata` when companion metadata is present

For `.pkml` models:

- the companion bundle is reported as supplemental evidence
- the model still needs a scientific profile sidecar to move beyond `exploratory`

## Authoring Conventions

Recommended row-authoring rules:

- use `variability-approach` for high-level variability methodology statements
- use `variability-propagation` for bounded distribution summaries or propagated outcome rows
- use `sensitivity-analysis` for local or global sensitivity rows
- use `residual-uncertainty` for unresolved uncertainty statements that are not quantitative propagation results

PBPK MCP now validates these rows conservatively. For example:

- `variability-approach` rows should include `method` or `summary`
- `variability-propagation` rows should include `method` or `summary`, plus `metric`, `targetOutput`, or `variedParameters`
- `variability-propagation` rows should also include at least one quantitative signal such as `value`, `lowerBound`, `upperBound`, `mean`, or `sd`; otherwise the row is treated as declared propagation scope rather than quantified propagation evidence
- `sensitivity-analysis` rows should include `method` or `summary`, plus `metric`, `targetOutput`, or `variedParameters`
- `residual-uncertainty` rows should include `summary`
- companion bundle metadata should include at least `bundleVersion` and `summary`

Missing fields are surfaced as warnings in both `validate_model_manifest` and `export_oecd_report`; the MCP does not silently upgrade weak rows into stronger uncertainty claims.

## Quantified vs Declared-Only Coverage

`uncertaintySummary.semanticCoverage` now exposes additive counters so downstream consumers do not need to infer quantification state from raw rows alone:

- `quantifiedRowCount`
- `declaredOnlyRowCount`
- `variabilityQuantificationStatus`

The intended interpretation is:

- `quantifiedRowCount` counts uncertainty rows that carry quantitative outputs recognized by the bridge
- `declaredOnlyRowCount` counts uncertainty rows that describe scope, method, or unresolved uncertainty without quantitative outputs
- `variabilityQuantificationStatus = quantified` is reserved for cases where `variability-propagation` rows actually include quantitative outputs
- `variabilityQuantificationStatus = declared-or-characterized` means variability was described, scoped, or bounded qualitatively, but not exported as quantified propagation evidence

## Template

A reusable starter template is included at:

```text
examples/uncertainty_evidence_bundle.template.json
```

Use that template as a starting point, then replace the placeholder rows and metadata with real model-specific uncertainty evidence.

## Important Boundary

Companion bundles improve traceability and portability, but they do not upgrade the scientific strength of the uncertainty evidence by themselves.

Bundled rows can represent internal sensitivity screens or bounded variability summaries without implying full uncertainty quantification, posterior inference, or externally reviewed qualification studies.
