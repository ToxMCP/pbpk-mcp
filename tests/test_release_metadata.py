from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "check_release_metadata.py"

spec = importlib.util.spec_from_file_location("pbpk_check_release_metadata_test", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load release metadata checker from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_check_release_metadata_test", module)
spec.loader.exec_module(module)

ReleaseMetadataError = module.ReleaseMetadataError
validate_release_metadata = module.validate_release_metadata


class ReleaseMetadataTests(unittest.TestCase):
    def test_workspace_release_metadata_is_consistent(self) -> None:
        summary = validate_release_metadata(WORKSPACE_ROOT)
        self.assertEqual(summary["version"], "0.3.5")
        self.assertEqual(summary["projectVersion"], summary["composeServiceVersion"])
        self.assertEqual(summary["projectVersion"], summary["releaseNoteVersion"])

    def test_mismatched_service_version_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pbpk_release_metadata_") as temp_dir:
            temp_root = Path(temp_dir)
            (temp_root / "src" / "mcp_bridge").mkdir(parents=True)
            (temp_root / "docs" / "releases").mkdir(parents=True)

            (temp_root / "pyproject.toml").write_text(
                '[project]\nname = "mcp-bridge"\nversion = "9.9.9"\n',
                encoding="utf-8",
            )
            shutil.copyfile(WORKSPACE_ROOT / "src" / "mcp_bridge" / "__init__.py", temp_root / "src" / "mcp_bridge" / "__init__.py")
            (temp_root / ".env.example").write_text('SERVICE_VERSION="9.9.8"\n', encoding="utf-8")
            (temp_root / "docker-compose.celery.yml").write_text(
                'services:\n  api:\n    environment:\n      SERVICE_VERSION: "9.9.9"\n',
                encoding="utf-8",
            )
            (temp_root / "README.md").write_text(
                "## What's new in v9.9.9\n\n| `SERVICE_VERSION` | `9.9.9` | Example |\n",
                encoding="utf-8",
            )
            (temp_root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## v9.9.9 - 2026-03-21\n",
                encoding="utf-8",
            )
            (temp_root / "docs" / "releases" / "v9.9.9.md").write_text(
                "# PBPK MCP v9.9.9\n",
                encoding="utf-8",
            )

            with self.assertRaises(ReleaseMetadataError):
                validate_release_metadata(temp_root)


if __name__ == "__main__":
    unittest.main()
