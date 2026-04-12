from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "release_readiness_check.py"
WAIT_SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "wait_for_runtime_ready.py"
spec = importlib.util.spec_from_file_location("pbpk_release_readiness_check", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_release_readiness_check", module)
spec.loader.exec_module(module)
wait_spec = importlib.util.spec_from_file_location("pbpk_wait_for_runtime_ready", WAIT_SCRIPT_PATH)
if wait_spec is None or wait_spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {WAIT_SCRIPT_PATH}")
wait_module = importlib.util.module_from_spec(wait_spec)
sys.modules.setdefault("pbpk_wait_for_runtime_ready", wait_module)
wait_spec.loader.exec_module(wait_module)

from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


class ReleaseReadinessScriptTests(unittest.TestCase):
    def test_build_auth_headers_uses_dev_secret(self) -> None:
        headers = module.build_auth_headers(
            bearer_token=None,
            auth_dev_secret="pbpk-local-dev-secret",
        )

        self.assertIn("authorization", headers)
        self.assertTrue(headers["authorization"].startswith("Bearer "))

    def test_build_auth_headers_uses_requested_role(self) -> None:
        headers = module.build_auth_headers(
            bearer_token=None,
            auth_dev_secret="pbpk-local-dev-secret",
            auth_role="admin",
        )

        token = headers["authorization"].split(" ", 1)[1]
        payload = jwt.decode(
            token,
            "pbpk-local-dev-secret",
            algorithms=["HS256"],
            options={"verify_aud": False},
        )

        self.assertEqual(payload["roles"], ["admin"])
        self.assertEqual(payload["sub"], "release-readiness-admin")

    def test_run_curated_manifest_gate_passes_for_bundled_models(self) -> None:
        payload = module.run_curated_manifest_gate()

        self.assertFalse(payload["gating"]["failed"])
        self.assertEqual(payload["summary"]["valid"], len(module.CURATED_WORKSPACE_MODELS))
        self.assertEqual(
            payload["summary"]["explicitNgraDeclarations"],
            len(module.CURATED_WORKSPACE_MODELS),
        )
        self.assertEqual(payload["gating"]["appliedChecks"], ["manifestStatus=valid", "curationSummary.ngraDeclarationsExplicit=true"])

    def test_release_and_wait_scripts_share_probe_inventory(self) -> None:
        self.assertEqual(module.REQUIRED_TOOLS, frozenset(module.release_probe_required_tools()))
        self.assertEqual(module.REQUIRED_SCHEMA_IDS, frozenset(module.published_schema_ids()))
        self.assertEqual(wait_module.DEFAULT_REQUIRED_TOOLS, module.release_probe_required_tools())

    def test_ospsuite_report_timeout_budget_is_raised_for_release_gate(self) -> None:
        self.assertGreaterEqual(module.OSPSUITE_LOAD_TIMEOUT_SECONDS, 300)
        self.assertGreaterEqual(module.OSPSUITE_REPORT_TIMEOUT_SECONDS, 300)
        self.assertGreaterEqual(module.ASYNC_REFERENCE_JOB_TIMEOUT_SECONDS, 300)


if __name__ == "__main__":
    unittest.main()
