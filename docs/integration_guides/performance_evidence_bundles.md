# Performance Evidence Bundles

## Purpose

PBPK MCP should not require model authors to hard-code performance evidence into bridge logic.

To keep the MCP reusable across different PBPK models, the runtime now supports optional companion JSON bundles for `performanceEvidence`. These bundles are intentionally narrow: they let a researcher attach structured observed-versus-predicted rows, predictive datasets, or external qualification rows next to a model file without changing the MCP code itself.

## Supported Companion Names

For either:

```text
/app/var/models/example/model.pkml
/app/var/models/example/model.R
```

the bridge and static manifest inspection now check, in order:

```text
/app/var/models/example/model.performance.json
/app/var/models/example/model.performance-evidence.json
/app/var/models/example/model.pkml.performance.json
/app/var/models/example/model.pkml.performance-evidence.json
/app/var/models/example/model.R.performance.json
/app/var/models/example/model.R.performance-evidence.json
```

## Payload Shape

The companion bundle may be:

- an object with top-level `rows`
- an object with `performanceEvidence.rows`
- a top-level array of evidence rows

Each row can use fields already recognized by `performanceEvidence`, for example:

- `id`
- `kind`
- `status`
- `metric`
- `targetOutput`
- `dataset`
- `observedValue`
- `predictedValue`
- `acceptanceCriterion`
- `evidenceLevel`
- `qualificationBasis`
- `notes`

Optional bundle-level metadata is also supported:

- `metadata.bundleVersion`
- `metadata.summary`
- `metadata.evidenceScope`
- `metadata.curator`
- `metadata.createdAt`
- `metadata.notes`

Optional explicit classification fields are also supported:

- `evidenceClass`
- `qualificationRelevance`
- `dataOrigin`

If these are omitted, the bridge infers conservative classes such as:

- `runtime-smoke`
- `internal-reference`
- `observed-vs-predicted`
- `predictive-dataset`
- `external-qualification`

## Runtime Behavior

When `export_oecd_report` runs, PBPK MCP merges performance evidence from:

1. `pbpk_performance_evidence(...)`
2. `profile.modelPerformance.evidence` / `evidenceRows`
3. the companion performance bundle

The report then computes conservative summary fields such as:

- `strongestEvidenceClass`
- `qualificationBoundary`
- `supportsObservedVsPredictedEvidence`
- `supportsPredictiveDatasetEvidence`
- `supportsExternalQualificationEvidence`
- `traceability`

`traceability` is additive. It summarizes whether the declared `modelPerformance` profile and exported evidence rows actually carry structured dataset records and explicit acceptance criteria.

This is meant to prevent runtime smoke or internal reference rows from being mistaken for predictive validation.

If companion bundle metadata is present, `export_oecd_report` also returns it as `performanceEvidence.bundleMetadata`.

## Static Manifest Behavior

`validate_model_manifest` now detects companion performance bundles statically.

For MCP-ready `R` models:

- a performance bundle can satisfy the performance-evidence requirement even if `pbpk_performance_evidence(...)` is not declared
- the manifest reports `hooks.performanceEvidenceSidecar = true`
- the manifest exposes `supplementalEvidence.performanceEvidenceSidecarPath`
- the manifest exposes `supplementalEvidence.performanceEvidenceRowCount`
- the manifest exposes `supplementalEvidence.performanceEvidenceBundleMetadata` when companion metadata is present

For `.pkml` models:

- the companion bundle is reported as supplemental evidence
- the model still needs a scientific profile sidecar to move beyond `exploratory`

## Authoring Conventions

Recommended row-authoring rules:

- Use `runtime-smoke` only for executable smoke or regression checks.
- Use `internal-reference` for internal baselines or regression datasets that are not external predictive validation.
- Use `observed-vs-predicted` only when an actual benchmark or study comparison exists.
- Use `predictive-dataset` when rows summarize a declared predictive evaluation dataset rather than a single observed/predicted pair.
- Use `external-qualification` only when a real external or regulatory qualification package exists.

PBPK MCP now validates these rows conservatively. For example:

- `observed-vs-predicted` rows should include `observedValue`, `predictedValue`, `dataset`, and `acceptanceCriterion`
- `predictive-dataset` rows should include `dataset` and `acceptanceCriterion`
- `external-qualification` rows should include a `dataset` or `qualificationBasis`, plus `acceptanceCriterion`
- companion bundle metadata should include at least `bundleVersion` and `summary`

Missing fields are surfaced as warnings in both `validate_model_manifest` and `export_oecd_report`; the MCP does not silently upgrade malformed rows into stronger evidence claims.

Recommended `acceptanceCriterion` content:

- name the metric and target output
- state the comparison rule
- state the threshold or pass condition
- state the scope or study context if relevant

Examples:

- `Relative error <= 20% for plasma Cmax in the declared adult IV study`
- `Geometric mean fold error within 2-fold across the packaged benchmark set`
- `Runtime simulation completes and returns finite concentration-time output`

If the scientific profile already declares `goodnessOfFit.datasetRecords`, `predictiveChecks.datasetRecords`, or section-level `acceptanceCriteria`, the bridge now preserves those as traceability counts in the exported performance summary even when the companion bundle is the only explicit row source.

## Template

A reusable starter template is included at:

```text
examples/performance_evidence_bundle.template.json
```

Use that template as a starting point, then replace the placeholder rows and metadata with real model-specific evidence.

## Important Boundary

Companion bundles improve traceability and portability, but they do not upgrade the scientific strength of the evidence by themselves.

If the rows only describe runtime checks or internal baselines, the OECD report will still classify them as runtime/internal evidence only. External predictive or qualification claims require real supporting datasets and appropriate qualification context.
