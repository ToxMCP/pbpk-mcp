# PBPK MCP Role in Exposure-led NGRA

For the shortest cross-service routing guide across the current ToxMCP family,
see [toxmcp_suite_index.md](./toxmcp_suite_index.md).

## Purpose

PBPK MCP is a PBPK execution, qualification, and handoff substrate inside an exposure-led NGRA workflow. It is not the whole workflow.

Its job is to make PBPK-side context, internal exposure estimates, qualification status, uncertainty state, and decision-adjacent handoff objects explicit enough that downstream human reviewers and orchestration layers can use them without overclaiming what PBPK MCP itself decided.

## What PBPK MCP Owns

- model discovery, manifest validation, load, execution, and result retrieval
- PBPK-side qualification summaries and executable-verification snapshots
- PBPK-side internal exposure estimates
- PBPK-side uncertainty summaries and uncertainty handoff objects
- typed references for external PoD and uncertainty-register inputs
- a BER-ready input bundle when the required PBPK-side and external inputs are present

## Upstream Dependencies

PBPK MCP depends on upstream scientific inputs that remain outside its ownership boundary:

- exposure estimates or externally defined dose scenarios
- in vitro ADME evidence and IVIVE parameterization choices
- bioactivity interpretation, point-of-departure selection, and NAM interpretation
- any broader weight-of-evidence synthesis that combines PBPK with hazard, AOP, or exposure-assessment layers

If those upstream inputs are weak, missing, or only partially traceable, PBPK MCP should surface that as a limitation rather than hiding it behind a clean run result.

## Downstream Outputs

PBPK MCP hands off:

- internal concentration metrics and output-selection context
- qualification status tied to declared context of use
- uncertainty summaries that separate declared, quantified, and still-missing PBPK-side uncertainty components
- population-support and extrapolation-boundary statements
- claim-boundary statements that say what kind of dosimetry or prioritization support is and is not justified

## What PBPK MCP Does Not Own

PBPK MCP is intentionally not:

- a standalone exposure-assessment engine
- a standalone IVIVE policy engine
- a standalone reverse-dosimetry solver for regulatory dose derivation
- a standalone weight-of-evidence or decision engine
- regulatory decision authority
- a substitute for hazard interpretation or AOP reasoning

## IVIVE and Dosimetry Boundary

The current repo should be read as follows:

- forward dosimetry support: PBPK MCP can translate an external dose scenario into PBPK-side internal exposure outputs
- reverse dosimetry support: PBPK MCP does not directly perform reverse dosimetry; it can support external workflows through explicit handoff objects and boundary metadata
- exposure-led prioritization: PBPK MCP can contribute PBPK-side substrate and context, but prioritization logic remains external
- direct regulatory dose derivation: not supported by PBPK MCP alone

These distinctions now surface directly in `pbpkQualificationSummary.workflowClaimBoundaries`.

## Population Variability Boundary

Population variability remains context-specific and often incomplete. PBPK MCP now surfaces:

- supported species
- supported physiology contexts
- supported life stages
- supported genotype or phenotype contexts when declared
- how variability is represented
- the extrapolation policy outside the declared population context

These statements live in `assessmentContext.populationSupport`. They are meant to slow down overgeneralization, not to imply that variability is comprehensively represented.

## Evidence Basis and No-direct-in-vivo Support

PBPK MCP now exposes a compact `pbpkQualificationSummary.evidenceBasis` block so downstream users can see, at minimum:

- what kind of evidence package is being claimed
- whether direct in vivo support is declared
- whether IVIVE linkage is declared or still external / unspecified
- whether parameterization basis needs separate provenance review
- what population-variability status is actually attached

This is intentionally conservative. If the model profile does not declare those details, the payload should say so rather than implying support.

## Human Review Rule

The core safety rule is simple:

- a successful simulation is not enough
- a BER-ready bundle is not enough
- an external PoD reference is not enough

Human reviewers still need to decide whether the upstream IVIVE linkage, exposure scenario, population assumptions, and non-animal evidence package are strong enough for the actual context of use.
