from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = WORKSPACE_ROOT / "schemas"
EXAMPLES_ROOT = SCHEMA_ROOT / "examples"
CAPABILITY_MATRIX_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "capability_matrix.json"
CONTRACT_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
PACKAGED_MODULE_PATH = WORKSPACE_ROOT / "src" / "mcp_bridge" / "contract" / "artifacts.py"

spec = importlib.util.spec_from_file_location("pbpk_contract_artifacts_test", PACKAGED_MODULE_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load packaged contract module from {PACKAGED_MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_contract_artifacts_test", module)
spec.loader.exec_module(module)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PackagedContractArtifactsTests(unittest.TestCase):
    def test_packaged_capability_matrix_matches_published_json(self) -> None:
        self.assertEqual(module.capability_matrix_document(), _load_json(CAPABILITY_MATRIX_PATH))

    def test_packaged_contract_manifest_matches_published_json(self) -> None:
        self.assertEqual(module.contract_manifest_document(), _load_json(CONTRACT_MANIFEST_PATH))

    def test_packaged_schema_documents_match_published_json(self) -> None:
        expected = {
            path.stem: _load_json(path) for path in sorted(SCHEMA_ROOT.glob("*.v*.json"))
        }
        self.assertEqual(module.schema_documents(), expected)

    def test_packaged_schema_examples_match_published_json(self) -> None:
        expected = {
            path.name.replace(".example.json", ""): _load_json(path)
            for path in sorted(EXAMPLES_ROOT.glob("*.json"))
        }
        self.assertEqual(module.schema_examples(), expected)

    def test_packaged_contract_manifest_declares_artifact_policy(self) -> None:
        manifest = module.contract_manifest_document()
        self.assertEqual(manifest["contractManifest"]["classification"], "normative")
        self.assertEqual(manifest["capabilityMatrix"]["classification"], "normative")
        self.assertTrue(all(entry["classification"] == "normative" for entry in manifest["schemas"]))
        self.assertTrue(all(entry["classification"] == "supporting" for entry in manifest["supportingArtifacts"]))
        self.assertTrue(
            any(entry["relativePath"] == "schemas/README.md" for entry in manifest["supportingArtifacts"])
        )
        self.assertTrue(
            any(
                entry["relativePath"] == "schemas/extraction-record.json"
                and entry["classification"] == "legacy-excluded"
                for entry in manifest["legacyArtifactPolicy"]
            )
        )


if __name__ == "__main__":
    unittest.main()
