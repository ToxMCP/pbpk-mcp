from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH = str(WORKSPACE_ROOT / "src")


def _run_module_probe(program: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        cwd=WORKSPACE_ROOT,
        env={**os.environ, "PYTHONPATH": PYTHONPATH},
        text=True,
    )
    return json.loads(completed.stdout)


class ImportFootprintTests(unittest.TestCase):
    def test_registry_base_does_not_import_tool_modules_eagerly(self) -> None:
        payload = _run_module_probe(
            """
import json
import sys
import mcp_bridge.tools.registry_base
print(json.dumps({
    "toolModulesLoaded": any(name.startswith("mcp_bridge.pbpk_tools.") for name in sys.modules),
}))
"""
        )
        self.assertFalse(payload["toolModulesLoaded"])

    def test_audit_package_does_not_import_jobs_eagerly(self) -> None:
        payload = _run_module_probe(
            """
import json
import sys
import mcp_bridge.audit
print(json.dumps({
    "trailImported": "mcp_bridge.audit.trail" in sys.modules,
    "jobsImported": "mcp_bridge.audit.jobs" in sys.modules,
}))
"""
        )
        self.assertTrue(payload["trailImported"])
        self.assertFalse(payload["jobsImported"])

    def test_auth_module_does_not_load_jwt_backends_eagerly(self) -> None:
        payload = _run_module_probe(
            """
import json
import sys
import mcp_bridge.security.auth
print(json.dumps({
    "joseLoaded": any(name == "jose" or name.startswith("jose.") for name in sys.modules),
    "simpleJwtLoaded": "mcp_bridge.security.simple_jwt" in sys.modules,
}))
"""
        )
        self.assertFalse(payload["joseLoaded"])
        self.assertFalse(payload["simpleJwtLoaded"])
