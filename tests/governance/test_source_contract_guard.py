"""Dedicated regression tests for the producer source-contract guard.

The guard validates each raw pbpkQualificationSummary against the producer's STRICT
emission contract (additionalProperties:false) at the TOP of run_gate, BEFORE any
projection. A packet that violates the contract — an undeclared/forbidden field, a
missing required field, or a value the producer enum cannot emit — BLOCKS
fail-closed (SOURCE_CONTRACT_VIOLATION) and is NEVER projected. This closes the
producer-emission-contract dead-arm class.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from governance import source_contract  # noqa: E402
from governance.errors import SOURCE_CONTRACT_VIOLATION  # noqa: E402

PRISTINE = REPO_ROOT / "governance" / "fixtures" / "pbpk-qualification-summary.pristine.json"
KIND = "pbpk_qualification_summary"


def _base() -> dict[str, Any]:
    return json.loads(PRISTINE.read_text(encoding="utf-8"))


def test_pristine_packet_satisfies_the_contract() -> None:
    assert source_contract.validate_source_packet(_base(), kind=KIND, corpus="x") is None


def test_forbidden_undeclared_field_is_rejected() -> None:
    fault = _base()
    fault["smuggledRegulatoryClaim"] = {"riskAssessmentReady": True}
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION
    assert "smuggledRegulatoryClaim" in v.message


def test_missing_required_field_is_rejected() -> None:
    fault = _base()
    del fault["riskAssessmentReady"]
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_out_of_enum_backend_is_rejected() -> None:
    fault = _base()
    fault["backend"] = "totally-validated-regulatory-engine"
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_wrong_objecttype_const_is_rejected() -> None:
    fault = _base()
    fault["objectType"] = "validatedRegulatoryDose.v1"
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_wrong_decisionboundary_const_is_rejected() -> None:
    fault = _base()
    fault["decisionBoundary"] = "ngra-decision-authority"
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_wrong_type_is_rejected() -> None:
    fault = _base()
    fault["riskAssessmentReady"] = "yes"  # producer emits a boolean
    v = source_contract.validate_source_packet(fault, kind=KIND, corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_unknown_kind_blocks_fail_closed() -> None:
    v = source_contract.validate_source_packet(_base(), kind="no_such_kind", corpus="x")
    assert v is not None
    assert v.code == SOURCE_CONTRACT_VIOLATION


def test_guard_rejects_forbidden_field_through_the_full_gate(tmp_path: Path) -> None:
    """End-to-end: a forbidden/undeclared-field packet is BLOCKED by the gate
    fail-closed (SOURCE_CONTRACT_VIOLATION, exit 1) and is NEVER projected. The
    corpus file is written UNDER the repo's governance/fixtures so run_gate (which
    resolves corpus paths against REPO_ROOT) loads it."""
    from scripts import scientific_invariants_gate as gate

    fixtures_dir = REPO_ROOT / "governance" / "fixtures"
    fault = _base()
    fault["smuggledRegulatoryClaim"] = {"riskAssessmentReady": True}
    rel = "governance/fixtures/_tmp_forbidden_field_packet.json"
    target = REPO_ROOT / rel
    try:
        target.write_text(json.dumps(fault), encoding="utf-8")
        rc = gate.run_gate([(rel, KIND)])
        assert rc == 1  # blocking
    finally:
        if target.exists():
            target.unlink()
