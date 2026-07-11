from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "esqlabs_models.py"
INDEX_PATH = WORKSPACE_ROOT / "var" / "models" / "esqlabs" / "index.json"

spec = importlib.util.spec_from_file_location("esqlabs_models", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("esqlabs_models", module)
spec.loader.exec_module(module)


class EsqlabsProvenanceTests(unittest.TestCase):
    def test_checked_in_inventory_is_machine_neutral_and_fail_closed(self) -> None:
        payload = json.loads(INDEX_PATH.read_text())
        self.assertEqual(payload["schemaVersion"], "pbpk-third-party-model-index.v1")
        self.assertEqual(payload["releaseDecision"], "not-approved-for-public-redistribution")
        self.assertEqual(len(payload["models"]), len(module.CATALOG))

        serialized = INDEX_PATH.read_text()
        for forbidden in ("/Users/", "/Volumes/", "/home/", "C:\\\\", "/HEAD/"):
            self.assertNotIn(forbidden, serialized)

        for entry in payload["models"]:
            self.assertRegex(entry["sourceCommit"], r"^[0-9a-f]{40}$")
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(entry["gitBlobSha1"], r"^[0-9a-f]{40}$")
            self.assertTrue(entry["originalRelativePath"].startswith("var/models/esqlabs/"))
            self.assertFalse(Path(entry["originalRelativePath"]).is_absolute())
            self.assertNotIn("localPath", entry)
            self.assertIn(
                entry["licenseReviewStatus"],
                {"unresolved", "license_identified_review_required"},
            )
            self.assertIn(
                entry["redistributionStatus"],
                {"exclude_from_public_release", "review_required"},
            )

    def test_public_repository_excludes_unapproved_model_assets(self) -> None:
        module.assert_public_tree_excludes_third_party_assets()

    def test_public_release_gate_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not approved"):
            module.assert_public_release_approved()

    def test_private_model_root_is_explicit(self) -> None:
        with mock.patch.dict(module.os.environ, {module.MODELS_ROOT_ENV: ""}):
            with self.assertRaisesRegex(RuntimeError, "not bundled"):
                module.resolve_models_root(None)

    def test_index_can_be_regenerated_from_an_explicit_private_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "models"
            for entry in module.CATALOG:
                path = root / entry["repo"] / entry["filename"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"synthetic:{entry['simulationId']}".encode())

            output = Path(directory) / "index.json"
            module.write_index(output, root)
            payload = json.loads(output.read_text())

        self.assertEqual(len(payload["models"]), len(module.CATALOG))
        self.assertTrue(
            all(
                entry["originalRelativePath"].startswith("var/models/esqlabs/")
                for entry in payload["models"]
            )
        )


if __name__ == "__main__":
    unittest.main()
