from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:  # pragma: no cover - exercised in the full contract env
    from mcp_bridge.contract import contract_manifest_document  # noqa: E402
    from mcp_bridge.routes.resources import router  # noqa: E402
    from mcp_bridge.routes import resources_base  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - local lightweight envs
    missing_name = exc.name or ""
    if missing_name != "fastapi" and missing_name != "mcp" and not missing_name.startswith("mcp_bridge"):
        raise
    router = None
    contract_manifest_document = None
    resources_base = None


class PackagedResourceRouteTests(unittest.TestCase):
    @unittest.skipIf(router is None, "fastapi is required for packaged route import checks")
    def test_packaged_router_exposes_full_generic_resource_surface(self) -> None:
        paths = {route.path for route in router.routes}
        expected = {
            "/mcp/resources/models",
            "/mcp/resources/simulations",
            "/mcp/resources/parameters",
            "/mcp/resources/schemas",
            "/mcp/resources/schemas/{schema_id}",
            "/mcp/resources/capability-matrix",
            "/mcp/resources/contract-manifest",
        }
        self.assertTrue(expected.issubset(paths))

    @unittest.skipIf(resources_base is None, "fastapi is required for packaged route import checks")
    def test_packaged_contract_manifest_is_authoritative_over_runtime_patch_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pbpk_contract_precedence_") as temp_dir:
            fake_manifest_path = Path(temp_dir) / "contract_manifest.json"
            fake_manifest = {"contractVersion": "stale-runtime-copy", "artifactCounts": {"schemas": 0}}
            fake_manifest_path.write_text(json.dumps(fake_manifest), encoding="utf-8")

            original_path = resources_base.CONTRACT_MANIFEST_PATH
            try:
                resources_base.CONTRACT_MANIFEST_PATH = fake_manifest_path
                manifest, manifest_sha256, last_modified = resources_base._contract_manifest_document()
            finally:
                resources_base.CONTRACT_MANIFEST_PATH = original_path

        packaged_manifest = contract_manifest_document()
        packaged_sha256 = hashlib.sha256(
            (json.dumps(packaged_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        ).hexdigest()
        self.assertEqual(manifest, packaged_manifest)
        self.assertEqual(manifest_sha256, packaged_sha256)
        self.assertEqual(last_modified, 0.0)


if __name__ == "__main__":
    unittest.main()
