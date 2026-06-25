#!/usr/bin/env python3
"""Regenerate the AUTHENTIC pristine fixture for the Track-B gate by running the
REAL producer (``_build_pbpk_qualification_summary`` in
``src/mcp_bridge/pbpk_tools/ingest_external_pbpk_bundle.py``) over a clean,
fit-for-context external PBPK bundle. This captures the producer's STRICT emission
surface (every field the seam stamps) — NOT a stale published schema or example.

Run with the package installed (``uv pip install -e .``) so ``mcp_bridge`` imports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcp_bridge.pbpk_tools.ingest_external_pbpk_bundle import (  # noqa: E402
    IngestExternalPbpkBundleRequest,
    _build_pbpk_qualification_summary,
)

# A CLEAN, fit-for-context external PBPK qualification bundle: a forward-dosimetry
# substrate qualified within its declared context, with full uncertainty evidence,
# that makes NO risk/regulatory decision claim (the producer's anti-overclaim
# posture). This is the pristine corpus the gate must keep GREEN.
CLEAN_INPUT = {
    "sourcePlatform": "Simcyp",
    "sourceVersion": "v22",
    "modelName": "compoundX-pbpk",
    "qualification": {
        "evidenceLevel": "fit-for-purpose",
        "qualificationLevel": "fit-for-purpose",
        "oecdReadiness": "fit-for-context",
        "verificationStatus": "verified-externally",
        "platformClass": "regulatory-grade-platform",
        "performanceEvidenceBoundary": "runtime-or-internal-evidence-only",
        "validationReferences": ["EMA-2018-PBPK-guideline", "FDA-2020-PBPK"],
        "checklistScore": 0.82,
        "missingEvidenceCount": 0,
        "label": "Qualified within declared forward-dosimetry context",
        "summary": "External PBPK qualification metadata normalized; not executed in PBPK MCP.",
        "state": "qualified-within-context",
    },
    "assessmentContext": {"intendedUse": "forward-dosimetry-substrate"},
    "internalExposure": {"metrics": {"cmax": {"value": 1.2}}, "route": "oral"},
    "uncertainty": {
        "status": "characterized",
        "source": "simcyp-uncertainty-module",
        "sources": ["parameter-sweep", "monte-carlo"],
        "issueCount": 0,
        "hasSensitivityAnalysis": True,
        "hasVariabilityApproach": True,
        "hasVariabilityPropagation": True,
        "hasResidualUncertainty": True,
        "summary": "Uncertainty characterized with propagated variability and explicit residual register.",
        "evidenceRowCount": 4,
        "totalEvidenceRows": 4,
        "rows": [
            {"kind": "variability-propagation", "quantitative": {"cv": 0.3}},
            {"kind": "sensitivity-analysis", "quantitative": {"range": [0.1, 0.9]}},
            {"kind": "residual-uncertainty", "quantitative": {"factor": 2.0}},
            {"kind": "variability-approach"},
        ],
    },
}


def main() -> int:
    req = IngestExternalPbpkBundleRequest.model_validate(CLEAN_INPUT)
    qual = _build_pbpk_qualification_summary(req)
    out = REPO_ROOT / "governance" / "fixtures" / "pbpk-qualification-summary.pristine.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(qual, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"[goldens] wrote {out.relative_to(REPO_ROOT)} ({len(qual)} top-level fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
