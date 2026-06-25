# ADR 0001 — Track-B scientific-invariants gate (vendored schema-spine)

* Status: Accepted
* Date: 2026-06-25
* Scope: `governance/`, `scripts/scientific_invariants_gate.py`,
  `scripts/vendor_verify.py`, `scripts/build_spine_projection_goldens.py`,
  `vendor/schema-spine/**`, `tests/governance/**`, the `scientific-invariants` CI job.
  (This ADR lives in the `docs/governance/adr/` namespace; it does NOT collide with
  `docs/adr/0001-audit-storage-boundary.md`.)

## Context

pbpk-mcp emits governance-relevant RELEASED objects whose job is to *qualify* a
PBPK simulation, NOT to make a risk/regulatory decision. The load-bearing
anti-overclaim surface is the **`pbpkQualificationSummary.v1`** object built by the
deterministic producer
`src/mcp_bridge/pbpk_tools/ingest_external_pbpk_bundle.py::_build_pbpk_qualification_summary`.
That object carries the producer's native anti-overclaim posture
(`decisionBoundary: no-ngra-decision-policy`, `supports.regulatoryDecision: false`,
`workflowClaimBoundaries.directRegulatoryDoseDerivation: not-supported`, an
export-block policy, and a caution summary).

The deterministic numeric PBPK simulation itself is not overclaim-able, but the
**qualification summary** (which asserts fitness/qualification) IS the governance
surface: a simulation qualification is not a validated regulatory dose, and a
screening-tier PBK output is not externally-validated PBPK or risk/regulatory
decision support. We want a **fail-closed regression gate** that BLOCKS if a future
change ever lets one of those overclaims into a released qualification summary,
grounded in the canonical, cross-repo ToxMCP **schema-spine** policy engine rather
than a bespoke per-repo checker.

## Decision

Add an **additive, advisory** Track-B scientific-invariants gate that:

1. **Vendors** the ToxMCP schema-spine policy engine, digest-pinned at
   `gitSha e0a6a0581efd8dfd5b10c2de14435d87769c5944`, under `vendor/schema-spine/`.
   `scripts/vendor_verify.py` (and the runtime bridge) recompute the SHA-256 of
   every vendored file against `VENDORED_FROM.json` and hard-fail on any mismatch /
   untracked / missing file. The engine logic (`policy-validator.mjs`) and all
   bundled schemas are **byte-identical** to the pinned spine source; only the flat
   re-export shim `index.mjs` and the single-object CLI `run-policy.mjs` are
   vendor-layout adapters (both digest-pinned in the manifest).

2. **Validates the producer's STRICT emission contract first**
   (`governance/source_contract.py` + `governance/emission-contracts/
   pbpk-qualification-summary-emission.v1.schema.json`). This is the
   `additionalProperties:false` tightening of the producer's plain-dict builder and
   of the STALE published `schemas/pbpkQualificationSummary.v1.json`
   (`additionalProperties:true`). EVERY field the real seam stamps is DECLARED here,
   verified against the AUTHENTIC emitted golden
   `governance/fixtures/pbpk-qualification-summary.pristine.json` captured by running
   the real producer (`scripts/build_spine_projection_goldens.py`). A packet that
   violates the contract (undeclared root field, missing required field, out-of-enum
   / wrong-const value the producer cannot emit) is a `SOURCE_CONTRACT_VIOLATION`
   that BLOCKS and is NEVER projected — closing the producer-emission-contract
   dead-arm class.

3. **Projects** each released `pbpkQualificationSummary` onto the spine
   **`InternalExposureSummary.v1`** shape from DECLARED producer fields only,
   using positive structured evidence (`governance/project_to_spine.py`). The
   projection is TOTAL: any field that cannot be faithfully mapped raises
   `PROJECTION_INCOMPLETE` (a fail-closed block), never a silent safe-default.
   Identifiers are NFKD + Mn/Cf normalized so a zero-width / combining-diacritic
   decoration cannot forge a distinct reference.

4. Runs the vendored engine over the projection via a **fail-closed Python bridge**
   (`governance/spine_bridge.py`): missing node / non-zero exit / empty or
   unparseable stdout / timeout → `ENGINE_UNAVAILABLE`; a tampered vendored file →
   `VENDOR_DIGEST_MISMATCH` (checked before the engine runs); an unrecognized
   `schemaId` → `UNRECOGNIZED_SPINE_SCHEMA_ID` (closing the engine's silent
   `valid:true` no-op for unknown ids). A `valid:true` is trusted ONLY after all
   guards pass.

The gate exits non-zero on any blocking code. It is **advisory** under the GitHub
Free plan (no required status checks). **PROMOTE-TO-BLOCKING:** when the repo gains
branch protection / rulesets, mark the `scientific-invariants` CI job a required
status check — the gate already exits non-zero on any blocking code.

## Advertised public-release-blocking scientific codes

Each is re-proven to bite on a PRODUCER-CONTRACT-VALID source fault
(jsonschema-valid against the strict emission contract), each plumbed from a
DECLARED producer field (see `tests/governance/test_scientific_invariants_adversarial.py`):

| Spine code | Declared producer driver(s) | Bites when |
| --- | --- | --- |
| `HTTK_SCREENING_NOT_PBPK` | `qualificationLevel` / `oecdReadiness` / `platformClass` → `pbkTier`; `riskAssessmentReady` / `state` → `modelQualificationStatus`; `supports.*` → `allowedDownstreamUses` | a screening-tier qualification declares external validation or authorizes risk/regulatory/decision downstream use |
| `INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY` | `supports.regulatoryDecision`; `workflowClaimBoundaries.directRegulatoryDoseDerivation` | the qualification authorizes a risk/regulatory/safe/legal/compliance downstream use |
| `INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED` | `performanceEvidenceBoundary`; `limitations`; `requiredExternalInputs`; `profileSource` | the qualification asserts fitness without substantive uncertainty / confidence-ceiling / parameter-provenance references |

On the pristine corpus all three are GREEN (the producer encodes the safe posture
natively).

## Honest N/A (advertised-but-dead avoided)

* **`INTERNAL_EXPOSURE_BASIS_REQUIRED`** (route / matrix / bindingBasis
  `not_assessed`) is HONEST-DROPPED. The `pbpkQualificationSummary` declares NO
  route / matrix / binding-basis field — those live on the SEPARATE
  `internalExposureEstimate.v1` released object. Projecting one as a mutable driver
  would synthesize a posture no declared qualification field carries (a dead arm).
  The projection stamps fixed faithful substrate values (`compartment:
  qualification-substrate`, route/matrix/binding fixed to the external-import
  substrate boundary) that the engine accepts, and the gate does NOT advertise this
  code. Re-introduction path: add a second corpus entry projecting the
  `internalExposureEstimate.v1` object (which DOES declare route/matrix/binding) and
  advertise the basis code there.

* **AI-provenance arm — N/A (deterministic).** pbpk-mcp's released objects are
  produced by DETERMINISTIC builders. The only LLM in the repo
  (`src/mcp_bridge/services/llm.py`) has **NO callers in `src/`** and its output
  enters **NO released object** (the `export_oecd_report` response `report` /
  `ngraObjects` / `qualificationState` / `dossierImprovementSignals` are all built by
  deterministic adapters and `reviewer_advisory.py`; the qualification / uncertainty
  summaries are deterministic dict builders). Therefore the gate projects NO
  `AssessmentRun`, advertises NO spine AI code
  (`AI_MODEL_IDENTITY_REQUIRED` / `HUMAN_REVIEW_REQUIRED_FOR_PUBLIC_AI_ASSESSMENT` /
  `AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW` / …), and there is no advertised-but-dead
  AI arm. **Re-introduction path:** if LLM-generated content ever flows into a
  released object, declare the producer-stamped AI/model-use/provenance field on that
  object's strict emission contract, project a faithful `AssessmentRun`
  (`aiUse=generated/assisted`, an `AiModelUseRecord` with the real model identity,
  `humanReviewRecords`), and advertise the AI codes proven on a real
  AI-provenance gap.

## Consequences

* The gate touches no PBPK `src/`, no `schemas/`, no contract artifacts, and does
  NOT dispatch or modify `.github/workflows/release-artifacts.yml` or
  `.github/workflows/model-smoke.yml`, so the existing release / model-smoke /
  runtime-contract gates are untouched.
* It adds an isolated `uv` Python side-toolchain + a Node runtime for the vendored
  engine in its own CI job.
* The vendored engine is byte-pinned and tamper-evident; bumping the spine requires
  re-vendoring at a new gitSha and re-running `vendor_verify.py --write`.
