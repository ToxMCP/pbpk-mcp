from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "workspace_model_smoke.py"
spec = importlib.util.spec_from_file_location("pbpk_workspace_model_smoke", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_workspace_model_smoke", module)
spec.loader.exec_module(module)


class WorkspaceModelSmokeScriptTests(unittest.TestCase):
    def test_build_auth_headers_uses_dev_secret(self) -> None:
        headers = module.build_auth_headers(
            bearer_token=None,
            auth_dev_secret="pbpk-local-dev-secret-32bytes-long",
            auth_role="operator",
        )

        self.assertIn("authorization", headers)
        self.assertTrue(headers["authorization"].startswith("Bearer "))

    def test_append_auth_hint_explains_operator_requirement(self) -> None:
        annotated = module.append_auth_hint(
            'http://127.0.0.1:8000/mcp/call_tool returned HTTP 403: {"error": {"message": "Insufficient permissions"}}',
            has_auth_headers=False,
        )

        self.assertIn("--auth-dev-secret", annotated)
        self.assertIn("operator or admin access", annotated)

    def test_append_auth_hint_leaves_other_errors_unchanged(self) -> None:
        error = "Timed out waiting for job abc"
        self.assertEqual(module.append_auth_hint(error, has_auth_headers=False), error)
        self.assertEqual(module.append_auth_hint(error, has_auth_headers=True), error)


if __name__ == "__main__":
    unittest.main()
