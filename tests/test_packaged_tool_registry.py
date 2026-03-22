from __future__ import annotations

import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:  # pragma: no cover - exercised in the full contract env
    from mcp_bridge.tools.registry import get_tool_registry  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - lightweight local envs
    missing_name = exc.name or ""
    if missing_name not in {"pydantic", "mcp"} and not missing_name.startswith("mcp_bridge"):
        raise
    get_tool_registry = None


class PackagedToolRegistryTests(unittest.TestCase):
    @unittest.skipIf(get_tool_registry is None, "packaged tool registry dependencies are not installed")
    def test_packaged_registry_exposes_base_tool_surface(self) -> None:
        registry = get_tool_registry()
        expected = {
            "load_simulation",
            "list_parameters",
            "get_parameter_value",
            "set_parameter_value",
            "run_simulation",
            "get_job_status",
            "calculate_pk_parameters",
            "run_population_simulation",
            "validate_simulation_request",
            "run_verification_checks",
            "get_population_results",
            "cancel_job",
            "run_sensitivity_analysis",
            "export_oecd_report",
        }
        self.assertTrue(expected.issubset(set(registry)))

    @unittest.skipIf(get_tool_registry is None, "packaged tool registry dependencies are not installed")
    def test_packaged_registry_excludes_patch_only_tools(self) -> None:
        registry = get_tool_registry()
        patch_only = {
            "discover_models",
            "validate_model_manifest",
            "get_results",
            "ingest_external_pbpk_bundle",
        }
        self.assertTrue(patch_only.isdisjoint(set(registry)))


if __name__ == "__main__":
    unittest.main()
