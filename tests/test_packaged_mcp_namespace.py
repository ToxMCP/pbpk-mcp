from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import unittest
import warnings
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
PYTHONPATH = str(SRC_ROOT)


def _run_probe(program: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        cwd=WORKSPACE_ROOT,
        env={**os.environ, "PYTHONPATH": PYTHONPATH},
        text=True,
    )
    return json.loads(completed.stdout)


class PackagedMcpNamespaceTests(unittest.TestCase):
    def test_canonical_pbpk_tool_imports_do_not_load_top_level_mcp(self) -> None:
        payload = _run_probe(
            """
import json
import sys
from mcp_bridge.pbpk_tools.discover_models import discover_models
from mcp_bridge.session_registry import SessionRegistry
print(json.dumps({
    "discoverModels": callable(discover_models),
    "sessionRegistry": SessionRegistry.__name__,
    "topLevelMcpLoaded": "mcp" in sys.modules,
}))
"""
        )
        self.assertTrue(payload["discoverModels"])
        self.assertEqual(payload["sessionRegistry"], "SessionRegistry")
        self.assertFalse(payload["topLevelMcpLoaded"])

    def test_transitional_mcp_namespace_exports_generic_pbpk_tools(self) -> None:
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                mcp_namespace = importlib.import_module("mcp")
        except ModuleNotFoundError as exc:  # pragma: no cover - lightweight local envs
            missing_name = exc.name or ""
            if missing_name not in {"pydantic", "mcp_bridge"} and not missing_name.startswith("mcp"):
                raise
            self.skipTest("packaged mcp namespace dependencies are not installed")

        expected = {
            "DiscoverableModelModel",
            "LoadSimulationRequest",
            "LoadSimulationResponse",
            "discover_models",
            "get_results",
            "ingest_external_pbpk_bundle",
            "load_simulation",
        }
        for name in expected:
            self.assertTrue(hasattr(mcp_namespace, name), name)
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))


if __name__ == "__main__":
    unittest.main()
