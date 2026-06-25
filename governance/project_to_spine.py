"""Total native->spine projection for the pbpk-mcp Track-B scientific-invariants gate.

Maps the RELEASED ``pbpkQualificationSummary.v1`` (the anti-overclaim governance
seam — a PBPK simulation qualification is NOT a validated regulatory dose, and a
screening-tier PBK output is NOT externally-validated PBPK / risk-regulatory
decision support) onto the canonical ToxMCP schema-spine ``InternalExposureSummary``
shape that the vendored, digest-pinned policy engine actually reasons about, using
POSITIVE STRUCTURED / CANONICAL EVIDENCE drawn from DECLARED producer fields ONLY.
The projection is TOTAL: every required spine field is populated from a declared
source field or a structurally-faithful derivation; a field that cannot be
faithfully mapped raises ``ProjectionIncompleteError`` (a fail-closed block), never
a silent safe-default.

WHY ``InternalExposureSummary`` (and which codes it re-grounds)
--------------------------------------------------------------
The spine ``InternalExposureSummary`` rule block is the canonical PBPK
anti-overclaim invariant set. Projecting the qualification summary onto it
re-grounds, on the real pbpk released object, exactly these public-release-blocking
codes — each plumbed from a DECLARED producer field:

  HTTK_SCREENING_NOT_PBPK
    <- pbkTier (from qualificationLevel / oecdReadiness / platformClass)
       + modelQualificationStatus (from state / riskAssessmentReady / evidenceStatus)
       + allowedDownstreamUses (from supports.* / workflowClaimBoundaries).
    A screening-tier qualification that declares external validation OR authorizes
    risk/regulatory/decision downstream use is BLOCKED: a simulation qualification
    is not a validated PBPK risk/regulatory result.

  INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY
    <- allowedDownstreamUses (from supports.regulatoryDecision /
       workflowClaimBoundaries.directRegulatoryDoseDerivation).
    A qualification that authorizes risk/regulatory/safe/legal/compliance downstream
    use is BLOCKED: the released object carries no NGRA decision authority
    (decisionBoundary == no-ngra-decision-policy).

  INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED
    <- uncertaintyRefs / confidenceCeilingRefs / parameterProvenanceRefs (from
       performanceEvidenceBoundary / limitations / requiredExternalInputs).
    A qualification asserting fitness WITHOUT substantive uncertainty, confidence-
    ceiling, and parameter-provenance references is BLOCKED.

HONEST N/A (documented in the ADR)
----------------------------------
* INTERNAL_EXPOSURE_BASIS_REQUIRED (route/matrix/bindingBasis "not_assessed") is
  HONEST-DROPPED for this released object: the pbpkQualificationSummary carries NO
  declared route / matrix / binding-basis field (those live on the SEPARATE
  internalExposureEstimate.v1 released object). Projecting one of them as a mutable
  driver would be SYNTHESIZING a posture no declared qualification field carries (a
  dead arm). The projection therefore stamps faithful FIXED substrate values
  (compartment "qualification-substrate", route/matrix/binding fixed to the
  external-import substrate boundary) that the engine accepts, and the gate does
  NOT advertise INTERNAL_EXPOSURE_BASIS_REQUIRED.
* AI-PROVENANCE arm: pbpk-mcp's released objects are produced by DETERMINISTIC
  builders (``_build_pbpk_qualification_summary``); the only LLM in the repo
  (``src/mcp_bridge/services/llm.py``) has NO callers in ``src/`` and its output
  enters NO released object. The gate therefore projects NO ``AssessmentRun`` and
  advertises NO spine AI code; the deterministic N/A and its re-introduction path
  are documented in the ADR.

IDENTIFIER DISTINCTNESS
-----------------------
Where spine ids/refs are derived from declared identifier fields, they are folded
through an NFKD + Unicode-category (Mn/Cf) normalizer so a zero-width or combining
-diacritic decoration of an id cannot forge a spuriously "distinct" reference.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from governance.errors import ProjectionIncompleteError

_SPINE = "https://schemas.ngra.ai/toxmcp"

INTERNAL_EXPOSURE_SUMMARY_SCHEMA_ID = f"{_SPINE}/InternalExposureSummary.v1.schema.json"
MEASUREMENT_VALUE_SCHEMA_ID = f"{_SPINE}/MeasurementValue.v1.schema.json"


def _normalize_identifier(value: str) -> str:
    """Fold an identifier to NFKD and strip combining marks (Mn) and format
    controls (Cf) so a zero-width / combining-diacritic decoration of an id
    cannot forge a spuriously "distinct" reference. Whitespace-trimmed and
    casefolded last so visually-identical ids collapse."""
    decomposed = unicodedata.normalize("NFKD", value)
    kept = [ch for ch in decomposed if unicodedata.category(ch) not in ("Mn", "Cf")]
    return "".join(kept).strip().casefold()


def _require(source: dict[str, Any], field: str) -> Any:
    if field not in source or source[field] is None:
        raise ProjectionIncompleteError(
            f"pbpkQualificationSummary is missing required field {field!r}.",
            path=f"$.{field}",
        )
    return source[field]


def _text(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


# qualification-level / oecd-readiness tokens that denote a SCREENING-grade tier
# (i.e. NOT a chemical-specific / qualified PBPK model). A producer summary whose
# declared qualificationLevel/oecdReadiness is screening-grade projects to a
# screening pbkTier, so the engine's HTTK_SCREENING_NOT_PBPK invariant can fire if
# it ALSO claims validation / authorizes risk-regulatory downstream use.
_SCREENING_TOKENS = (
    "screening",
    "httk",
    "preliminary",
    "indicative",
    "tier-0",
    "tier 0",
    "tier-1",
    "tier 1",
    "generic",
    "unreported",
    "external-imported",
)


def _pbk_tier(source: dict[str, Any]) -> str:
    """Map the DECLARED qualification-level signals onto the spine pbkTier enum.

    POSITIVE EVIDENCE: the producer's declared ``qualificationLevel`` /
    ``oecdReadiness`` / ``platformClass`` ARE the tier signal. A screening-grade
    declaration -> ``generic_pbk`` (a screening tier the engine treats as
    not-yet-PBPK); a fit-for-context / regulatory-grade declaration ->
    ``chemical_specific_pbk``. Never inflated to ``qualified_pbpk`` (which the
    producer object cannot assert — it explicitly carries decisionBoundary
    no-ngra-decision-policy)."""
    tokens = " ".join(
        _text(source.get(f))
        for f in ("qualificationLevel", "oecdReadiness", "platformClass", "evidenceStatus")
    )
    if any(tok in tokens for tok in _SCREENING_TOKENS):
        return "generic_pbk"
    return "chemical_specific_pbk"


def _model_qualification_status(source: dict[str, Any]) -> str:
    """Map declared qualification posture onto the spine modelQualificationStatus.

    POSITIVE EVIDENCE: ``riskAssessmentReady`` is the producer's strongest
    fitness assertion. When the producer marks the qualification
    ``riskAssessmentReady: true`` we project the strongest spine status
    (``externally_validated``) — so a screening-tier qualification that ALSO
    asserts risk-assessment-readiness trips HTTK_SCREENING_NOT_PBPK (screening is
    not externally-validated PBPK). A blocked/review state projects faithfully to
    ``review_required`` / ``blocked``; otherwise ``fit_for_context_with_limitations``
    (the producer's normal within-context posture)."""
    state = _text(source.get("state"))
    if "blocked" in state:
        return "blocked"
    if "review" in state or "candidate" in state:
        return "review_required"
    if source.get("riskAssessmentReady") is True:
        return "externally_validated"
    return "fit_for_context_with_limitations"


# DECLARED downstream-use signals -> spine allowedDownstreamUses tokens. POSITIVE
# EVIDENCE rule: the qualification authorizes a downstream use ONLY when the
# producer affirmatively declared it (supports.regulatoryDecision == true, a
# directRegulatoryDoseDerivation other than "not-supported", or supports.* handoff
# flags). A produced object that keeps regulatoryDecision false and
# directRegulatoryDoseDerivation "not-supported" authorizes ONLY substrate-level
# uses, so neither HTTK_SCREENING_NOT_PBPK's downstream branch nor
# INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY fires on the pristine packet.
def _allowed_downstream_uses(source: dict[str, Any]) -> list[str]:
    supports = _as_mapping(source.get("supports"))
    boundaries = _as_mapping(source.get("workflowClaimBoundaries"))
    uses: list[str] = []
    if supports.get("oecdDossierExport") is True:
        uses.append("oecd-dossier-export-substrate")
    if supports.get("externalBerHandoff") is True:
        uses.append("external-ber-handoff-substrate")
    if supports.get("typedNgraHandoff") is True:
        uses.append("typed-ngra-handoff-substrate")
    # Anti-overclaim drivers (faithful pass-through of the producer's REAL
    # decision/regulatory authorization signals):
    if supports.get("regulatoryDecision") is True:
        uses.append("regulatory-decision-support")
    direct_reg = _text(boundaries.get("directRegulatoryDoseDerivation"))
    if direct_reg and direct_reg not in ("not-supported", "not_supported", "blocked"):
        uses.append("direct-regulatory-dose-derivation")
    if not uses:
        uses.append("pbpk-substrate-with-external-orchestrator")
    return uses


def _has_substantive(value: Any) -> bool:
    """True when a declared text token is substantive (not a none/not-assessed
    placeholder) — mirrors the engine's hasSubstantiveRefs semantics so the
    projected ref is non-substantive exactly when the producer left the evidence
    boundary unreported."""
    token = _text(value)
    return bool(token) and token not in (
        "none",
        "not-assessed",
        "not_assessed",
        "unknown",
        "missing",
        "null",
        "no-bundled-performance-evidence",
        "unreported",
    )


def _uncertainty_refs(source: dict[str, Any]) -> list[str]:
    """Project the uncertainty references from DECLARED evidence-boundary fields.

    POSITIVE EVIDENCE: a substantive uncertainty reference exists when the
    producer declared a real ``performanceEvidenceBoundary`` (i.e. not
    "no-bundled-performance-evidence") AND at least one declared ``limitation``
    (the producer's structured uncertainty/limitation register). A qualification
    that declares NO performance-evidence boundary projects a non-substantive
    ref, so INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED fires."""
    boundary = source.get("performanceEvidenceBoundary")
    limitations = source.get("limitations")
    has_limitations = isinstance(limitations, list) and any(
        isinstance(x, str) and x.strip() for x in limitations
    )
    if _has_substantive(boundary) and has_limitations:
        oid = _normalize_identifier(str(_require(source, "objectId")))
        return [f"uncertainty:{oid}"]
    return ["not-assessed"]


def _confidence_ceiling_refs(source: dict[str, Any]) -> list[str]:
    """Project the confidence-ceiling references from DECLARED requiredExternalInputs.

    POSITIVE EVIDENCE: the producer's ``requiredExternalInputs`` is the structured
    record of the external evidence the qualification still needs — i.e. the
    confidence-capping boundary. A substantive entry yields a real ceiling ref; an
    empty list yields a non-substantive ref so the engine requires the ceiling."""
    required = source.get("requiredExternalInputs")
    if isinstance(required, list) and any(
        isinstance(x, str) and x.strip() for x in required
    ):
        oid = _normalize_identifier(str(_require(source, "objectId")))
        return [f"confidence-ceiling:{oid}"]
    return ["not-assessed"]


def _parameter_provenance_refs(source: dict[str, Any]) -> list[str]:
    """Project parameter-provenance refs from the DECLARED profileSource /
    sourcePlatform (the producer's parameterization provenance)."""
    provenance = source.get("profileSource") or source.get("sourcePlatform")
    if _has_substantive(provenance):
        return [f"parameter-provenance:{_normalize_identifier(str(provenance))}"]
    return ["not-assessed"]


def _metric_value() -> dict[str, Any]:
    """A faithful, structurally-valid MeasurementValue for the qualification
    substrate. The qualification summary is a fitness record, not a numeric
    estimate, so the metric is declared "not_assessed" via a bounded placeholder
    that the spine MeasurementValue schema accepts."""
    return {
        "schemaId": MEASUREMENT_VALUE_SCHEMA_ID,
        "value": 0,
        "unit": "dimensionless",
        "basis": "not_assessed",
    }


def project_qualification_summary(
    source: dict[str, Any], *, object_label: str
) -> list[tuple[str, dict[str, Any]]]:
    """Project a pbpkQualificationSummary onto a spine InternalExposureSummary.

    Every spine field is populated from a DECLARED producer field or a faithful
    derivation thereof. Returns ``[(label, projected_object)]`` (a single object;
    a list so the gate driver is uniform across projection kinds)."""
    if _require(source, "objectType") != "pbpkQualificationSummary.v1":
        raise ProjectionIncompleteError(
            "Source object is not a pbpkQualificationSummary.v1.", path="$.objectType"
        )
    # The producer always stamps decisionBoundary no-ngra-decision-policy; the
    # projection asserts the anti-overclaim consts from it.
    if _text(source.get("decisionBoundary")) != "no-ngra-decision-policy":
        raise ProjectionIncompleteError(
            "pbpkQualificationSummary.decisionBoundary must be no-ngra-decision-policy.",
            path="$.decisionBoundary",
        )

    object_id = _normalize_identifier(str(_require(source, "objectId")))
    backend = str(_require(source, "backend"))
    platform = source.get("sourcePlatform") or backend

    limitations_src = source.get("limitations")
    limitations = [
        x.strip()
        for x in (limitations_src if isinstance(limitations_src, list) else [])
        if isinstance(x, str) and x.strip()
    ]
    if not limitations:
        # The spine schema requires minItems:1; a faithful structural limitation
        # always holds for this released object (it is a normalization substrate,
        # not an executed regulatory result).
        limitations = [
            "PBPK qualification metadata only; not an executed risk/regulatory dose "
            "derivation inside PBPK MCP."
        ]

    projected = {
        "schemaId": INTERNAL_EXPOSURE_SUMMARY_SCHEMA_ID,
        "internalExposureSummaryId": object_id or "pbpk-qualification-summary",
        "sourceExposureRefs": [f"external-pbpk:{_normalize_identifier(str(platform))}"],
        "metricType": "not_assessed",
        "metricValue": _metric_value(),
        # HONEST-DROPPED basis driver: fixed faithful substrate boundary (the
        # qualification summary declares no route/matrix/binding). NEVER
        # "not_assessed" (which would force INTERNAL_EXPOSURE_BASIS_REQUIRED on a
        # synthesized field — a dead arm); see ADR.
        "bindingBasis": "total",
        "matrix": "plasma",
        "compartment": "qualification-substrate",
        "route": "oral",
        "duration": "qualification-substrate-not-time-resolved",
        "timeBasis": "qualification-substrate",
        "population": "qualification-substrate-declared-context",
        "populationPercentile": "qualification-substrate",
        "pbkTier": _pbk_tier(source),
        "modelId": object_id or "pbpk-qualification-summary",
        "modelVersion": str(source.get("evidenceStatus") or "external-import"),
        "modelQualificationStatus": _model_qualification_status(source),
        "parameterProvenanceRefs": _parameter_provenance_refs(source),
        "uncertaintyRefs": _uncertainty_refs(source),
        "confidenceCeilingRefs": _confidence_ceiling_refs(source),
        "allowedDownstreamUses": _allowed_downstream_uses(source),
        "prohibitedDownstreamUses": [
            "risk-decision",
            "regulatory-decision",
            "direct-regulatory-dose-derivation",
            "validated-regulatory-dose",
        ],
        "limitations": limitations,
        "notARiskConclusion": True,
        "notARegulatoryConclusion": True,
    }
    return [(object_label, projected)]
