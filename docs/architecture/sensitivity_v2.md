# Sensitivity v2 Design Note

This note defines the intended next step after the current local one-at-a-time sensitivity screen.

## Current Boundary

`run_sensitivity_analysis` in the current public contract is a local perturbation screen:

- one parameter at a time
- percent deltas around the captured baseline parameter state
- deterministic PK summaries per scenario
- screening-only interpretation

It is useful for quick reviewer-facing uncertainty signals, but it is not a global sensitivity method.

## Candidate v2 Methods

Preferred order:

1. Morris / elementary-effects screening
2. bounded Saltelli/Sobol first-order and total-order indices
3. only later, heavier variance-based workflows for explicitly bounded use cases

Reasoning:

- Morris offers a practical first global-screening step with bounded runtime
- Sobol-style methods are more informative but can become expensive quickly
- the first public v2 method should fit the existing MCP worker/runtime budget

## Request Shape

Recommended additive tool shape:

- keep the existing `run_sensitivity_analysis` contract unchanged
- add a new tool later, for example `run_global_sensitivity_analysis`

Expected request elements:

- `modelPath`
- `simulationId`
- `parameters[*].path`
- `parameters[*].distribution`
- `parameters[*].bounds`
- `parameters[*].unit`
- `sampling.method`
- `sampling.sampleCount`
- `metrics`
- optional `seed`

## Response Shape

The future response should keep provenance explicit:

- baseline parameter capture
- sampling method and sample count
- per-parameter first-order and total-order indices
- execution failures and rejected samples
- interpretation boundary stating whether interactions were screened or fully decomposed

## Runtime Constraints

The public tool should refuse requests that exceed conservative limits for:

- parameter count
- sample count
- expected simulation budget
- artifact size

Heavy result tables should use retained chunked artifacts rather than forcing all raw runs into a single JSON payload.

## Qualification Boundary

Sensitivity v2 should remain bounded by default:

- global-sensitivity outputs are supporting evidence, not automatic qualification upgrades
- they should not widen direct regulatory-dose or decision semantics
- report language must keep runtime evidence, predictive evidence, and uncertainty evidence distinct

## Exit Criteria For Production

Do not expose the first v2 tool until:

- runtime limits are enforced
- result provenance is stable
- at least one reference model has repeatable tests
- the report/export wording is explicit about method and boundary
