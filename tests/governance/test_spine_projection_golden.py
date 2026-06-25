"""Golden projection + fail-closed bridge tests for the pbpk-mcp Track-B gate.

Pins the SHAPE of the spine InternalExposureSummary projected from the pristine
pbpkQualificationSummary (so a silent projection drift is caught), confirms the
projection is TOTAL / faithful, and exercises the bridge's fail-closed guards
(vendor-digest integrity, recognized schemaId, malformed/unknown input).
"""

from __future__ import annotations

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
from governance import spine_bridge as bridge  # noqa: E402
from governance.errors import (  # noqa: E402
    UNRECOGNIZED_SPINE_SCHEMA_ID,
    ProjectionIncompleteError,
)

PRISTINE = REPO_ROOT / "governance" / "fixtures" / "pbpk-qualification-summary.pristine.json"

_node_required = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the vendored spine policy engine",
)


def _base() -> dict[str, Any]:
    return json.loads(PRISTINE.read_text(encoding="utf-8"))


def test_projection_is_total_and_targets_internal_exposure_summary() -> None:
    projected = proj.project_qualification_summary(_base(), object_label="pristine")
    assert len(projected) == 1
    _label, obj = projected[0]
    assert obj["schemaId"] == proj.INTERNAL_EXPOSURE_SUMMARY_SCHEMA_ID
    # Every spine-required field is present (TOTAL projection).
    for field in (
        "internalExposureSummaryId",
        "sourceExposureRefs",
        "metricType",
        "metricValue",
        "bindingBasis",
        "matrix",
        "compartment",
        "route",
        "duration",
        "timeBasis",
        "population",
        "populationPercentile",
        "pbkTier",
        "modelId",
        "modelVersion",
        "modelQualificationStatus",
        "parameterProvenanceRefs",
        "uncertaintyRefs",
        "confidenceCeilingRefs",
        "allowedDownstreamUses",
        "prohibitedDownstreamUses",
        "limitations",
        "notARiskConclusion",
        "notARegulatoryConclusion",
    ):
        assert field in obj, f"projection missing required spine field {field!r}"
    # Anti-overclaim consts are positively asserted.
    assert obj["notARiskConclusion"] is True
    assert obj["notARegulatoryConclusion"] is True


def test_pristine_projection_is_faithful_clean() -> None:
    """The pristine packet maps to a non-screening tier, within-context status, and
    substrate-only downstream uses (no risk/regulatory authorization)."""
    _label, obj = proj.project_qualification_summary(_base(), object_label="x")[0]
    assert obj["pbkTier"] == "chemical_specific_pbk"
    assert "regulatory-decision-support" not in obj["allowedDownstreamUses"]
    assert "direct-regulatory-dose-derivation" not in obj["allowedDownstreamUses"]
    assert obj["uncertaintyRefs"] != ["not-assessed"]
    assert obj["confidenceCeilingRefs"] != ["not-assessed"]


def test_projection_blocks_on_wrong_objecttype() -> None:
    fault = _base()
    fault["objectType"] = "somethingElse.v1"
    with pytest.raises(ProjectionIncompleteError):
        proj.project_qualification_summary(fault, object_label="x")


def test_projection_blocks_on_missing_required_field() -> None:
    fault = _base()
    del fault["objectId"]
    with pytest.raises(ProjectionIncompleteError):
        proj.project_qualification_summary(fault, object_label="x")


@_node_required
def test_pristine_projection_passes_the_engine() -> None:
    _label, obj = proj.project_qualification_summary(_base(), object_label="x")[0]
    result = bridge.validate_object(obj)
    assert result.valid, result.blocking_codes


@_node_required
def test_bridge_rejects_unrecognized_schema_id_fail_closed() -> None:
    """An object whose schemaId the engine does not reason about must NOT slip
    through as valid:true (the engine's silent no-op) — the bridge blocks it."""
    obj = {"schemaId": "https://schemas.ngra.ai/toxmcp/NotARealSchema.v1.schema.json"}
    result = bridge.validate_object(obj)
    assert not result.valid
    assert UNRECOGNIZED_SPINE_SCHEMA_ID in result.blocking_codes


@_node_required
def test_vendor_digests_are_intact() -> None:
    """The fail-closed digest guard reports no tamper on the pristine vendor tree."""
    assert bridge.verify_vendor_digests() is None
