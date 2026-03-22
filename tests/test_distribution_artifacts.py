from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "check_distribution_artifacts.py"

spec = importlib.util.spec_from_file_location("pbpk_check_distribution_artifacts_test", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load distribution checker from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_check_distribution_artifacts_test", module)
spec.loader.exec_module(module)

build_release_artifact_report = module._build_release_artifact_report
required_sdist_paths = module._required_sdist_paths
stage_source_tree = module._stage_source_tree


def _workspace_version() -> str:
    pyproject_text = (WORKSPACE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "(?P<version>\d+\.\d+\.\d+)"$', pyproject_text, flags=re.MULTILINE)
    if match is None:  # pragma: no cover - test fixture guard
        raise AssertionError("Unable to determine workspace version from pyproject.toml")
    return match.group("version")


class DistributionArtifactTests(unittest.TestCase):
    def test_required_sdist_paths_include_release_metadata_script(self) -> None:
        required = required_sdist_paths(WORKSPACE_ROOT)
        self.assertIn("scripts/check_release_metadata.py", required)

    def test_release_artifact_report_links_contract_manifest_and_hashes(self) -> None:
        version = _workspace_version()
        with tempfile.TemporaryDirectory(prefix="pbpk_release_report_") as temp_dir:
            temp_root = Path(temp_dir)
            sdist_path = temp_root / f"mcp_bridge-{version}.tar.gz"
            wheel_path = temp_root / f"mcp_bridge-{version}-py3-none-any.whl"
            sdist_path.write_bytes(b"sdist-bytes")
            wheel_path.write_bytes(b"wheel-bytes")

            report = build_release_artifact_report(WORKSPACE_ROOT, sdist_path, wheel_path)

        manifest = json.loads(
            (WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["packageVersion"], version)
        self.assertEqual(report["contractVersion"], manifest["contractVersion"])
        self.assertEqual(
            report["contractManifest"]["relativePath"],
            manifest["contractManifest"]["relativePath"],
        )
        self.assertEqual(
            report["capabilityMatrix"]["relativePath"],
            manifest["capabilityMatrix"]["relativePath"],
        )
        self.assertEqual(report["artifactCounts"]["schemas"], manifest["artifactCounts"]["schemas"])
        self.assertEqual(report["artifactCounts"]["supporting"], manifest["artifactCounts"]["supporting"])
        self.assertEqual(report["artifacts"]["sdist"]["filename"], sdist_path.name)
        self.assertEqual(report["artifacts"]["wheel"]["filename"], wheel_path.name)
        self.assertGreater(report["artifacts"]["sdist"]["sizeBytes"], 0)
        self.assertGreater(report["artifacts"]["wheel"]["sizeBytes"], 0)

    def test_stage_source_tree_excludes_local_virtualenv_and_codex_scratch_dirs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pbpk_stage_src_") as source_dir, tempfile.TemporaryDirectory(
            prefix="pbpk_stage_dst_"
        ) as destination_dir:
            source_root = Path(source_dir)
            destination_root = Path(destination_dir)

            (source_root / "README.md").write_text("example\n", encoding="utf-8")
            (source_root / ".venv").mkdir()
            (source_root / ".venv" / "pyvenv.cfg").write_text("home = /tmp/python\n", encoding="utf-8")
            (source_root / ".tmp_codex_overlay").mkdir()
            (source_root / ".tmp_codex_overlay" / "pyvenv.cfg").write_text(
                "home = /tmp/python\n",
                encoding="utf-8",
            )
            (source_root / "src" / "mcp_bridge.egg-info").mkdir(parents=True)
            (source_root / "src" / "mcp_bridge.egg-info" / "PKG-INFO").write_text(
                "metadata\n",
                encoding="utf-8",
            )

            staged_root = stage_source_tree(source_root, destination_root)

            self.assertTrue((staged_root / "README.md").exists())
            self.assertFalse((staged_root / ".venv").exists())
            self.assertFalse((staged_root / ".tmp_codex_overlay").exists())
            self.assertFalse((staged_root / "src" / "mcp_bridge.egg-info").exists())

    def test_stage_source_tree_excludes_runtime_only_and_local_private_assets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pbpk_stage_src_") as source_dir, tempfile.TemporaryDirectory(
            prefix="pbpk_stage_dst_"
        ) as destination_dir:
            source_root = Path(source_dir)
            destination_root = Path(destination_dir)

            (source_root / "README.md").write_text("example\n", encoding="utf-8")
            (source_root / "var" / "models").mkdir(parents=True)
            (source_root / "var" / "models" / "example.pkml").write_text("pkml\n", encoding="utf-8")
            (source_root / "cisplatin_models").mkdir()
            (source_root / "cisplatin_models" / "local_model.R").write_text("model\n", encoding="utf-8")
            (source_root / "docs" / "figures").mkdir(parents=True)
            (source_root / "docs" / "figures" / "figure.png").write_bytes(b"png")
            (source_root / "reports").mkdir()
            (source_root / "reports" / "note.txt").write_text("report\n", encoding="utf-8")

            staged_root = stage_source_tree(source_root, destination_root)

            self.assertTrue((staged_root / "README.md").exists())
            self.assertFalse((staged_root / "var").exists())
            self.assertFalse((staged_root / "cisplatin_models").exists())
            self.assertFalse((staged_root / "docs" / "figures").exists())
            self.assertFalse((staged_root / "reports").exists())


if __name__ == "__main__":
    unittest.main()
