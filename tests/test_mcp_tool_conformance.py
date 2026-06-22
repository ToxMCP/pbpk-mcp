"""MCP conformance baseline: assert the advertised tool surface is exactly as expected.

This is the Track-A *mcp-conformance baseline* gate, implemented in the
transport-correct form for this server. pbpk-mcp does **not** expose a stdio MCP
entrypoint; its MCP transport is the Streamable HTTP JSON-RPC surface mounted at
``/mcp`` (see ``mcp_bridge.routes.jsonrpc``). The proven fleet-reference stdio
form (``mcp.client.stdio.stdio_client``) therefore does not apply literally, so
this gate spawns the built application in a fresh process-local server, drives
the *real* MCP ``tools/list`` JSON-RPC method through the FastAPI client, and
asserts the advertised tool-name set equals an expected checked-in literal.

Why this is not redundant with existing tests:

* ``tests/test_mcp_jsonrpc_protocol.py`` exercises ``tools/list`` but only
  asserts ``len(tools) > 0`` and per-tool schema shape -- it does NOT pin the
  exact tool-name set, so a renamed / added / removed tool slips through.
* ``tests/test_packaged_tool_registry.py`` asserts only that an expected set is
  a *subset* of the in-process registry dict; a subset check cannot catch an
  *extra* (rogue) tool, and it inspects the registry object rather than the live
  advertised MCP surface.

This gate closes both gaps by pinning the *live advertised* surface exactly.

pbpk-mcp role-filters the advertised tool surface (``_handle_list_tools`` drops
descriptors whose ``roles`` do not intersect the caller's roles), so the
advertised surface is auth-context dependent. The gate pins BOTH the
least-privilege viewer/anonymous surface and the full operator+admin surface so
that a drift in either the tool set OR the role gating is caught.

MAINTAINERS: the two literals below (``EXPECTED_PRIVILEGED_TOOLS`` and
``EXPECTED_VIEWER_TOOLS``) are hand-maintained. When you add, remove, rename, or
re-scope (change ``roles`` on) an MCP tool in
``src/mcp_bridge/tools/registry_base.py``, update the matching literal here in
the SAME change. A failure here is a deliberate, attributed signal that the
advertised MCP tool surface drifted from this committed expectation.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.app import create_app  # noqa: E402
from mcp_bridge.config import AppConfig  # noqa: E402


# Dev-only HS256 secret used solely to mint a local privileged token for this
# in-process conformance check. It never leaves this test process.
_DEV_SECRET = "pbpk-conformance-dev-secret-32bytes-long!!"


# The full advertised MCP tool surface for an operator+admin caller. This is the
# complete set of registered MCP tools. Keep in lockstep with
# ``src/mcp_bridge/tools/registry_base.py``.
EXPECTED_PRIVILEGED_TOOLS = {
    "calculate_pk_parameters",
    "cancel_job",
    "discover_models",
    "export_oecd_report",
    "get_job_status",
    "get_parameter_value",
    "get_population_results",
    "get_results",
    "ingest_external_pbpk_bundle",
    "list_parameters",
    "load_simulation",
    "run_parameter_consistency_check",
    "run_population_simulation",
    "run_sensitivity_analysis",
    "run_simulation",
    "run_verification_checks",
    "set_parameter_value",
    "validate_model_manifest",
    "validate_simulation_request",
}

# The least-privilege (viewer / anonymous) advertised surface. This is the
# privileged surface MINUS the six operator/admin-only tools that carry no
# ``viewer`` role: load_simulation, set_parameter_value, run_simulation,
# run_population_simulation, run_sensitivity_analysis, cancel_job.
EXPECTED_VIEWER_TOOLS = {
    "calculate_pk_parameters",
    "discover_models",
    "export_oecd_report",
    "get_job_status",
    "get_parameter_value",
    "get_population_results",
    "get_results",
    "ingest_external_pbpk_bundle",
    "list_parameters",
    "run_parameter_consistency_check",
    "run_verification_checks",
    "validate_model_manifest",
    "validate_simulation_request",
}


def _mint_privileged_token() -> str:
    """Mint a short-lived dev HS256 token carrying the privileged role set."""

    try:  # pragma: no cover - exercised when python-jose is installed
        from jose import jwt
    except ImportError:  # pragma: no cover - constrained-env fallback
        from mcp_bridge.security.simple_jwt import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "sub": "conformance-gate",
            "roles": ["viewer", "operator", "admin"],
            "iat": now,
            "exp": now + 3600,
        },
        _DEV_SECRET,
        algorithm="HS256",
    )


class McpToolConformanceTests(unittest.TestCase):
    """Pin the live, advertised MCP ``tools/list`` surface to an expected set."""

    def _viewer_client(self) -> TestClient:
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": True,
                "audit_enabled": False,
                "service_version": "0.5.0-conformance",
            }
        )
        return TestClient(create_app(config=config))

    def _privileged_client(self) -> TestClient:
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": False,
                "auth_dev_secret": _DEV_SECRET,
                "audit_enabled": False,
                "service_version": "0.5.0-conformance",
            }
        )
        return TestClient(create_app(config=config))

    @staticmethod
    def _list_tool_names(client: TestClient, headers: dict | None = None) -> set[str]:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers=headers or {},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "result" in body, body
        return {tool["name"] for tool in body["result"]["tools"]}

    def test_privileged_tools_list_matches_expected_set_exactly(self) -> None:
        with self._privileged_client() as client:
            advertised = self._list_tool_names(
                client, headers={"Authorization": f"Bearer {_mint_privileged_token()}"}
            )

        self.assertEqual(
            advertised,
            EXPECTED_PRIVILEGED_TOOLS,
            "Advertised MCP tools/list (operator+admin) drifted from the committed "
            "expectation. Missing: "
            f"{sorted(EXPECTED_PRIVILEGED_TOOLS - advertised)}; "
            f"unexpected: {sorted(advertised - EXPECTED_PRIVILEGED_TOOLS)}. "
            "If this change is intended, update EXPECTED_PRIVILEGED_TOOLS in "
            "tests/test_mcp_tool_conformance.py alongside the registry change.",
        )

    def test_viewer_tools_list_matches_expected_set_exactly(self) -> None:
        with self._viewer_client() as client:
            advertised = self._list_tool_names(client)

        self.assertEqual(
            advertised,
            EXPECTED_VIEWER_TOOLS,
            "Advertised MCP tools/list (viewer/anonymous) drifted from the committed "
            "expectation. Missing: "
            f"{sorted(EXPECTED_VIEWER_TOOLS - advertised)}; "
            f"unexpected: {sorted(advertised - EXPECTED_VIEWER_TOOLS)}. "
            "If this change is intended, update EXPECTED_VIEWER_TOOLS in "
            "tests/test_mcp_tool_conformance.py alongside the registry change.",
        )

    def test_viewer_surface_is_the_privileged_surface_minus_privileged_only_tools(
        self,
    ) -> None:
        # Internal consistency guard so the two literals above cannot silently
        # diverge in a way that hides a role-gating regression.
        self.assertTrue(EXPECTED_VIEWER_TOOLS.issubset(EXPECTED_PRIVILEGED_TOOLS))
        privileged_only = EXPECTED_PRIVILEGED_TOOLS - EXPECTED_VIEWER_TOOLS
        self.assertEqual(
            privileged_only,
            {
                "load_simulation",
                "set_parameter_value",
                "run_simulation",
                "run_population_simulation",
                "run_sensitivity_analysis",
                "cancel_job",
            },
        )


if __name__ == "__main__":
    unittest.main()
