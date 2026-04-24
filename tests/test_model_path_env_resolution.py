from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.pbpk_tools.load_simulation import resolve_model_path  # noqa: E402
from mcp_bridge.model_catalog import resolve_model_roots as resolve_catalog_roots  # noqa: E402


def _load_validate_model_manifests_module():
    spec = importlib.util.spec_from_file_location(
        "validate_model_manifests_script",
        WORKSPACE_ROOT / "scripts" / "validate_model_manifests.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load validate_model_manifests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModelPathEnvResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validate_model_manifests = _load_validate_model_manifests_module()

    def test_load_simulation_prefers_canonical_model_path_env(self) -> None:
        with tempfile.TemporaryDirectory() as canonical_dir, tempfile.TemporaryDirectory() as legacy_dir:
            canonical_model = Path(canonical_dir) / "example.r"
            canonical_model.write_text("pbpk_model_profile <- function() list()", encoding="utf-8")
            legacy_model = Path(legacy_dir) / "example.r"
            legacy_model.write_text("pbpk_model_profile <- function() list()", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {
                    "ADAPTER_MODEL_PATHS": canonical_dir,
                    "MCP_MODEL_SEARCH_PATHS": legacy_dir,
                },
                clear=True,
            ):
                resolved = resolve_model_path(str(canonical_model))

            self.assertEqual(resolved, canonical_model.resolve())

    def test_model_catalog_prefers_canonical_model_path_env(self) -> None:
        with tempfile.TemporaryDirectory() as canonical_dir, tempfile.TemporaryDirectory() as legacy_dir:
            with mock.patch.dict(
                os.environ,
                {
                    "ADAPTER_MODEL_PATHS": canonical_dir,
                    "MCP_MODEL_SEARCH_PATHS": legacy_dir,
                },
                clear=True,
            ):
                roots = resolve_catalog_roots()

            self.assertEqual(roots, (Path(canonical_dir).resolve(),))

    def test_validate_model_manifests_prefers_canonical_model_path_env(self) -> None:
        with tempfile.TemporaryDirectory() as canonical_dir, tempfile.TemporaryDirectory() as legacy_dir:
            with mock.patch.dict(
                os.environ,
                {
                    "ADAPTER_MODEL_PATHS": canonical_dir,
                    "MCP_MODEL_SEARCH_PATHS": legacy_dir,
                },
                clear=True,
            ):
                roots = self.validate_model_manifests.resolve_model_roots()

            self.assertEqual(roots, (Path(canonical_dir).resolve(),))


if __name__ == "__main__":
    unittest.main()
