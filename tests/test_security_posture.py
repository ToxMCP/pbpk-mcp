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
from mcp_bridge.security.auth import AuthError, JWTValidator  # noqa: E402
from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


class SecurityPostureTests(unittest.TestCase):
    def _build_client(self, **overrides: object) -> TestClient:
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": False,
                "audit_enabled": False,
                "service_version": "0.4.2-test",
                **overrides,
            }
        )
        return TestClient(create_app(config=config))

    def test_anonymous_mode_exposes_only_viewer_tools(self) -> None:
        with self._build_client(auth_allow_anonymous=True) as client:
            response = client.get("/mcp/list_tools")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-PBPK-Security-Mode"), "anonymous-development")
        tool_names = {item["name"] for item in response.json()["tools"]}
        self.assertIn("discover_models", tool_names)
        self.assertIn("export_oecd_report", tool_names)
        self.assertNotIn("load_simulation", tool_names)
        self.assertNotIn("run_simulation", tool_names)

    def test_public_contract_artifacts_remain_readable_without_auth(self) -> None:
        with self._build_client() as client:
            schemas = client.get("/mcp/resources/schemas")
            models = client.get("/mcp/resources/models")

        self.assertEqual(schemas.status_code, 200)
        self.assertEqual(models.status_code, 401)

    def test_metrics_are_not_available_to_anonymous_viewers(self) -> None:
        with self._build_client(auth_allow_anonymous=True) as client:
            response = client.get("/metrics")

        self.assertEqual(response.status_code, 403)

    def test_console_routes_are_retired_in_local_development(self) -> None:
        with self._build_client() as client:
            page = client.get("/console")
            asset = client.get("/console/assets/app.js")
            api = client.get("/console/api/samples")
            stale_static_path = client.get("/console/static/app.js")

        self.assertEqual(page.status_code, 404)
        self.assertEqual(asset.status_code, 404)
        self.assertEqual(api.status_code, 404)
        self.assertEqual(stale_static_path.status_code, 404)

    def test_console_routes_stay_retired_outside_local_development(self) -> None:
        config = AppConfig.model_validate(
            {
                "environment": "production",
                "auth_allow_anonymous": False,
                "audit_enabled": False,
                "service_version": "0.4.2-test",
                "auth_issuer_url": "https://issuer.example",
                "auth_audience": "pbpk-mcp",
                "auth_jwks_url": "https://issuer.example/.well-known/jwks.json",
            }
        )
        with TestClient(create_app(config=config)) as client:
            page = client.get("/console")
            asset = client.get("/console/assets/app.js")
            api = client.get("/console/api/samples")

        self.assertEqual(page.status_code, 404)
        self.assertEqual(asset.status_code, 404)
        self.assertEqual(api.status_code, 404)

    def test_critical_tools_still_require_confirmation_with_operator_token(self) -> None:
        secret = "test-dev-secret-must-be-32-bytes"
        token = jwt.encode(
            {
                "sub": "operator-user",
                "roles": ["operator"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            secret,
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {token}"}

        with self._build_client(auth_allow_anonymous=True, auth_dev_secret=secret) as client:
            response = client.post(
                "/mcp/call_tool",
                headers=headers,
                json={
                    "tool": "load_simulation",
                    "arguments": {"filePath": "/tmp/not-validated-yet.pkml"},
                },
            )

        self.assertEqual(response.status_code, 428)

    def test_replayed_jti_token_is_rejected(self) -> None:
        secret = "test-dev-secret-must-be-32-bytes"
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": False,
                "auth_dev_secret": secret,
                "audit_enabled": False,
                "service_version": "0.4.2-test",
            }
        )
        validator = JWTValidator(config)
        token = jwt.encode(
            {
                "sub": "viewer-user",
                "roles": ["viewer"],
                "jti": f"reusable-{time.time_ns()}",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            secret,
            algorithm="HS256",
        )

        first = validator.validate(token)
        self.assertEqual(first.subject, "viewer-user")
        with self.assertRaises(AuthError) as ctx:
            validator.validate(token)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Replay detected for token identifier")

    def test_tokens_without_jti_can_be_reused_across_requests(self) -> None:
        secret = "test-dev-secret-must-be-32-bytes"
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": False,
                "auth_dev_secret": secret,
                "audit_enabled": False,
                "service_version": "0.5.0-test",
            }
        )
        validator = JWTValidator(config)
        token = jwt.encode(
            {
                "sub": "viewer-user",
                "roles": ["viewer"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            secret,
            algorithm="HS256",
        )

        first = validator.validate(token)
        second = validator.validate(token)
        self.assertEqual(first.subject, "viewer-user")
        self.assertEqual(second.subject, "viewer-user")
        self.assertIsNone(second.token_id)


if __name__ == "__main__":
    unittest.main()
