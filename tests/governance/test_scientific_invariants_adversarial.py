"""Adversarial per-code bite proofs for the pbpk-mcp Track-B gate.

Every advertised public-release-blocking scientific code MUST bite on a PRODUCER-
CONTRACT-VALID source fault (a pbpkQualificationSummary that PASSES the strict
emission contract, then trips the code through the faithful projection), each
plumbed from a DECLARED producer field. These tests are the executable proof of
the "no advertised-but-dead code" property: clean -> declared-field fault ->
attributed red -> revert -> green.

They drive the FULL gate path (source-contract guard -> projection -> vendored
spine engine via the fail-closed bridge), so a regression that silently neutered a
code (e.g. a projection that stopped passing a declared overclaim signal through)
turns these red.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from governance import project_to_spine as proj  # noqa: E402
from governance import source_contract as sc  # noqa: E402
from governance import spine_bridge as bridge  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the vendored spine policy engine",
)

PRISTINE = REPO_ROOT / "governance" / "fixtures" / "pbpk-qualification-summary.pristine.json"
KIND = "pbpk_qualification_summary"


def _base() -> dict[str, Any]:
    return json.loads(PRISTINE.read_text(encoding="utf-8"))


def _engine_codes(packet: dict[str, Any]) -> set[str]:
    """Run the FULL gate path and return the engine's blocking codes.

    Asserts the packet is producer-contract-VALID first (so the bite is on a real
    producer-emittable fault, not a schema-forbidden smuggle the guard would catch).
    """
    contract_violation = sc.validate_source_packet(packet, kind=KIND, corpus="adversarial")
    assert contract_violation is None, (
        f"fault packet must be producer-contract-VALID, got {contract_violation}"
    )
    projected = proj.project_qualification_summary(packet, object_label="adversarial")
    codes: set[str] = set()
    for _label, obj in projected:
        result = bridge.validate_object(obj)
        codes.update(result.blocking_codes)
    return codes


# --- pristine is GREEN -------------------------------------------------------


def test_pristine_corpus_is_green() -> None:
    assert _engine_codes(_base()) == set()


# --- HTTK_SCREENING_NOT_PBPK -------------------------------------------------


def test_screening_tier_claiming_validation_bites() -> None:
    """A producer summary that declares a SCREENING qualificationLevel/oecdReadiness
    but riskAssessmentReady:true (screening claiming externally-validated PBPK) is
    BLOCKED — driven by declared qualificationLevel/oecdReadiness + riskAssessmentReady."""
    fault = _base()
    fault["qualificationLevel"] = "screening-tier-0"
    fault["oecdReadiness"] = "screening"
    fault["riskAssessmentReady"] = True
    codes = _engine_codes(fault)
    assert "HTTK_SCREENING_NOT_PBPK" in codes
    # revert -> green
    assert _engine_codes(_base()) == set()


# --- INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY --------------------------


def test_regulatory_decision_support_bites() -> None:
    """A producer summary whose supports.regulatoryDecision is true authorizes a
    regulatory decision downstream use and is BLOCKED — driven by the declared
    supports.regulatoryDecision flag."""
    fault = _base()
    fault["supports"] = dict(fault["supports"])
    fault["supports"]["regulatoryDecision"] = True
    codes = _engine_codes(fault)
    assert "INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY" in codes


def test_direct_regulatory_dose_derivation_bites() -> None:
    """A producer summary whose workflowClaimBoundaries.directRegulatoryDose
    Derivation is anything other than 'not-supported' authorizes a direct
    regulatory dose derivation and is BLOCKED."""
    fault = _base()
    fault["workflowClaimBoundaries"] = dict(fault["workflowClaimBoundaries"])
    fault["workflowClaimBoundaries"]["directRegulatoryDoseDerivation"] = "supported"
    codes = _engine_codes(fault)
    assert "INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY" in codes


# --- INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED ----------------------------------


def test_missing_uncertainty_evidence_bites() -> None:
    """A producer summary that declares NO bundled performance evidence, no
    required external inputs, and no profile source projects non-substantive
    uncertainty / confidence-ceiling / parameter-provenance refs and is BLOCKED."""
    fault = _base()
    fault["performanceEvidenceBoundary"] = "no-bundled-performance-evidence"
    fault["requiredExternalInputs"] = []
    fault["profileSource"] = "none"
    codes = _engine_codes(fault)
    assert "INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED" in codes


# --- every advertised code is reachable (no dead arm) ------------------------


def test_every_advertised_code_is_reachable() -> None:
    """Sweep: the union of codes bitten across the declared-field faults equals the
    advertised set, so NO advertised code is dead and NO bitten code is unadvertised
    (besides the screening+regulatory co-fire which is a real double violation)."""
    from scripts.scientific_invariants_gate import BLOCKING_SCIENTIFIC_CODES

    bitten: set[str] = set()

    f1 = _base()
    f1["qualificationLevel"] = "screening-tier-0"
    f1["oecdReadiness"] = "screening"
    f1["riskAssessmentReady"] = True
    bitten |= _engine_codes(f1)

    f2 = _base()
    f2["supports"] = dict(f2["supports"])
    f2["supports"]["regulatoryDecision"] = True
    bitten |= _engine_codes(f2)

    f3 = _base()
    f3["performanceEvidenceBoundary"] = "no-bundled-performance-evidence"
    f3["requiredExternalInputs"] = []
    f3["profileSource"] = "none"
    bitten |= _engine_codes(f3)

    assert BLOCKING_SCIENTIFIC_CODES <= bitten, (
        f"advertised-but-dead code(s): {BLOCKING_SCIENTIFIC_CODES - bitten}"
    )
