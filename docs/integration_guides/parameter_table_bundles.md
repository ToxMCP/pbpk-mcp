# Parameter Table Bundles

## Purpose

OECD-style PBPK reporting needs more than a flat parameter name/value list. Reviewers often need to see units, provenance, distributions or summary statistics, study conditions, and the rationale for why a parameter value or bound exists.

PBPK MCP now supports optional companion JSON bundles for `parameterTable` so model authors can attach that richer metadata next to either `.pkml` or MCP-ready `.R` models without hard-coding every parameter row into bridge logic.

## Supported Companion Names

For either:

```text
/app/var/models/example/model.pkml
/app/var/models/example/model.R
```

the bridge and static manifest inspection now check, in order:

```text
/app/var/models/example/model.parameters.json
/app/var/models/example/model.parameter-table.json
/app/var/models/example/model.pkml.parameters.json
/app/var/models/example/model.pkml.parameter-table.json
/app/var/models/example/model.R.parameters.json
/app/var/models/example/model.R.parameter-table.json
```

## Payload Shape

The companion bundle may be:

- an object with top-level `rows`
- an object with `parameterTable.rows`
- a top-level array of parameter rows

Each row can use fields already recognized by `parameterTable`, for example:

- `path`
- `display_name` or `displayName`
- `unit`
- `category`
- `value`
- `source`
- `sourceType`
- `sourceCitation`
- `sourceTable`
- `evidenceType`
- `rationale`
- `motivation`
- `distribution`
- `mean`
- `sd` or `standardDeviation`
- `lowerBound`
- `upperBound`
- `experimentalConditions`, `studyConditions`, or `testConditions`
- `notes`

Optional bundle-level metadata is also supported:

- `metadata.bundleVersion`
- `metadata.summary`
- `metadata.evidenceScope`
- `metadata.curator`
- `metadata.createdAt`
- `metadata.notes`

## Runtime Behavior

When `export_oecd_report` runs, PBPK MCP builds `parameterTable` from:

1. `pbpk_parameter_table(...)` when present
2. the runtime parameter catalog or enumerated backend parameter state
3. the companion parameter-table bundle

Rows are merged by parameter `path`. The bundle can therefore enrich runtime rows rather than replace them.

The exported `parameterTable` now also includes:

- `source`
- `sources`
- `sidecarPath`
- `bundleMetadata`
- `issues`
- `issueCount`
- `coverage`

`coverage` is a compact completeness summary for OECD-style reporting. It currently counts how many matched rows include:

- units
- sources
- source citations
- distributions or summary statistics
- experimental/study conditions
- rationale or motivation

## Static Manifest Behavior

`validate_model_manifest` now detects companion parameter-table bundles statically.

For MCP-ready `R` models:

- a parameter-table bundle can satisfy the parameter-table requirement even if `pbpk_parameter_table(...)` is not declared
- the manifest reports `hooks.parameterTableSidecar = true`
- the manifest exposes `supplementalEvidence.parameterTableSidecarPath`
- the manifest exposes `supplementalEvidence.parameterTableRowCount`
- the manifest exposes `supplementalEvidence.parameterTableBundleMetadata` when companion metadata is present

For `.pkml` models:

- the companion bundle is reported as supplemental evidence
- the model still needs a scientific profile sidecar to move beyond `exploratory`

## Authoring Conventions

Recommended row-authoring rules:

- always use the runtime `path` as the stable key
- keep `unit` aligned with the exposed MCP/runtime unit
- use `source`, `sourceCitation`, and `sourceTable` to show where the parameter came from
- use `distribution`, `mean`, `sd`, `lowerBound`, and `upperBound` only when those values are actually defined for the declared context
- use `experimentalConditions` to capture study matrix, species/life stage, route, assay conditions, or other scope statements that matter for reuse
- use `rationale` or `motivation` to explain why a default, bound, or override exists

PBPK MCP validates these bundles conservatively. For example:

- bundle metadata should include at least `bundleVersion` and `summary`
- each row must include a `path`
- missing provenance/statistics/condition fields are surfaced through `issues` and `coverage`; the MCP does not silently treat a sparse table as dossier-complete

This is intentionally descriptive, not a hidden score. Richer parameter-table metadata improves traceability and reviewability, but it does not by itself change `qualificationState` or `oecdChecklistScore`.

## Template

A reusable starter template is included at:

```text
examples/parameter_table_bundle.template.json
```

Use that template as a starting point, then replace the placeholder rows and metadata with real model-specific parameter provenance.

## Important Boundary

Companion bundles improve portability and OECD-style reporting completeness, but they do not manufacture evidence.

A row with a path and a citation is still not the same thing as a validated parameter-estimation package. Use the bundle to make parameter assumptions explicit, not to overstate their qualification level.
