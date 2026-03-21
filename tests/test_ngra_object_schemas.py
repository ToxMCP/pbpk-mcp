from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = WORKSPACE_ROOT / "schemas"
EXAMPLES_ROOT = SCHEMA_ROOT / "examples"
PATCH_ROOT = WORKSPACE_ROOT / "patches"
TOOL_PATH = PATCH_ROOT / "mcp" / "tools" / "ingest_external_pbpk_bundle.py"
HAS_PYDANTIC = importlib.util.find_spec("pydantic") is not None
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None

if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

SCHEMA_FILES = {
    "assessmentContext": "assessmentContext.v1.json",
    "pbpkQualificationSummary": "pbpkQualificationSummary.v1.json",
    "uncertaintySummary": "uncertaintySummary.v1.json",
    "uncertaintyHandoff": "uncertaintyHandoff.v1.json",
    "uncertaintyRegisterReference": "uncertaintyRegisterReference.v1.json",
    "internalExposureEstimate": "internalExposureEstimate.v1.json",
    "pointOfDepartureReference": "pointOfDepartureReference.v1.json",
    "berInputBundle": "berInputBundle.v1.json",
}

if HAS_PYDANTIC:
    spec = importlib.util.spec_from_file_location("pbpk_patch_external_bundle_schema_test", TOOL_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise RuntimeError(f"Unable to load patch module from {TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("pbpk_patch_external_bundle_schema_test", module)
    spec.loader.exec_module(module)
    IngestExternalPbpkBundleRequest = module.IngestExternalPbpkBundleRequest
    ingest_external_pbpk_bundle = module.ingest_external_pbpk_bundle


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema is required for schema validation tests")
class NgraObjectSchemaTests(unittest.TestCase):
    def test_schemas_are_valid(self) -> None:
        for filename in SCHEMA_FILES.values():
            schema = _load_json(SCHEMA_ROOT / filename)
            Draft202012Validator.check_schema(schema)

    def test_examples_validate_against_schemas(self) -> None:
        for _, filename in SCHEMA_FILES.items():
            schema = _load_json(SCHEMA_ROOT / filename)
            example_name = filename.replace(".json", ".example.json")
            example = _load_json(EXAMPLES_ROOT / example_name)
            Draft202012Validator(schema).validate(example)


@unittest.skipUnless(
    HAS_PYDANTIC and HAS_JSONSCHEMA,
    "pydantic and jsonschema are required for runtime schema validation",
)
class RuntimeNgraObjectSchemaTests(unittest.TestCase):
    def test_external_bundle_ngra_objects_validate_against_schemas(self) -> None:
        payload = ingest_external_pbpk_bundle(
            IngestExternalPbpkBundleRequest(
                sourcePlatform="GastroPlus",
                sourceVersion="10.1",
                modelName="Example external PBPK",
                assessmentContext={
                    "contextOfUse": {"regulatoryUse": "research-only"},
                    "scientificPurpose": "Tier 1 internal exposure screening",
                    "decisionContext": "BER handoff",
                    "domain": {"species": "human", "route": "oral", "population": "adult"},
                    "targetOutput": "Plasma|Parent|Concentration",
                },
                internalExposure={
                    "targetOutput": "Plasma|Parent|Concentration",
                    "species": "human",
                    "route": "oral",
                    "population": "adult",
                    "metrics": {
                        "cmax": {"value": 3.2, "unit": "uM"},
                        "tmax": {"value": 1.5},
                        "auc0Tlast": {"value": 10.5, "unit": "uM*h"},
                    },
                },
                qualification={
                    "evidenceLevel": "L2",
                    "verificationStatus": "checked",
                    "platformClass": "commercial",
                    "performanceEvidenceBoundary": "runtime-or-internal-evidence-only",
                },
                uncertainty={
                    "status": "declared",
                    "summary": "Imported uncertainty summary",
                    "evidenceRows": [
                        {
                            "kind": "variability-propagation",
                            "status": "declared",
                            "method": "population simulation",
                            "metric": "cmax",
                            "targetOutput": "Plasma|Parent|Concentration",
                            "lowerBound": 2.7,
                            "upperBound": 3.8,
                        },
                        {
                            "kind": "residual-uncertainty",
                            "status": "declared",
                            "summary": "Residual external-dose mapping uncertainty",
                        },
                    ],
                },
                uncertaintyRegister={
                    "ref": "unc-reg-001",
                    "source": "assessment-workbench",
                    "scope": "tier-1-systemic",
                },
                pod={
                    "ref": "pod-001",
                    "source": "httr-benchmark",
                    "metric": "cmax",
                    "unit": "uM",
                    "basis": "true-dose-adjusted",
                },
                trueDoseAdjustment={
                    "applied": True,
                    "basis": "free-concentration",
                    "summary": "Normalized to free concentration",
                },
                comparisonMetric="cmax",
            )
        ).model_dump(by_alias=True)

        ngra_objects = payload["ngraObjects"]
        for key, filename in SCHEMA_FILES.items():
            schema = _load_json(SCHEMA_ROOT / filename)
            Draft202012Validator(schema).validate(ngra_objects[key])


if __name__ == "__main__":
    unittest.main()
