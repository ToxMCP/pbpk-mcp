from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "s3_audit_smoke.py"
spec = importlib.util.spec_from_file_location("pbpk_s3_audit_smoke", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_s3_audit_smoke", module)
spec.loader.exec_module(module)

from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


class S3AuditSmokeScriptTests(unittest.TestCase):
    def test_build_auth_headers_uses_dev_secret(self) -> None:
        headers = module.build_auth_headers(
            bearer_token=None,
            auth_dev_secret="pbpk-local-dev-secret",
            auth_role="operator",
        )

        token = headers["authorization"].split(" ", 1)[1]
        payload = jwt.decode(
            token,
            "pbpk-local-dev-secret",
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        self.assertEqual(payload["sub"], "s3-audit-smoke")
        self.assertEqual(payload["roles"], ["operator"])

    def test_build_s3_client_supports_endpoint_and_path_style(self) -> None:
        sentinel_client = object()
        with mock.patch.object(module, "BotoConfig", return_value="path-style-config") as config_cls:
            with mock.patch.object(module.boto3, "client", return_value=sentinel_client) as client:
                built = module.build_s3_client(
                    endpoint_url="http://127.0.0.1:9000",
                    region="us-east-1",
                    force_path_style=True,
                    access_key_id="minioadmin",
                    secret_access_key="minioadmin",
                )

        self.assertIs(built, sentinel_client)
        config_cls.assert_called_once_with(s3={"addressing_style": "path"})
        client.assert_called_once_with(
            "s3",
            endpoint_url="http://127.0.0.1:9000",
            region_name="us-east-1",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            config="path-style-config",
        )


if __name__ == "__main__":
    unittest.main()
