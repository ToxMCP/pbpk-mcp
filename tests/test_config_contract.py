from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.config import AppConfig, config_env_warnings  # noqa: E402


class ConfigContractTests(unittest.TestCase):
    def test_documented_env_aliases_are_loaded(self) -> None:
        env = {
            "SERVICE_VERSION": "0.4.2-test",
            "R_PATH": "/usr/bin/R",
            "R_HOME": "/usr/lib/R",
            "R_LIBS": "/opt/R/libs",
            "MCP_MODEL_SEARCH_PATHS": "/models:/workspace/models",
            "ADAPTER_TIMEOUT_SECONDS": "15",
            "AUDIT_TRAIL_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.adapter_r_path, "/usr/bin/R")
        self.assertEqual(config.adapter_r_home, "/usr/lib/R")
        self.assertEqual(config.adapter_r_libs, "/opt/R/libs")
        self.assertEqual(config.adapter_model_paths, ("/models", "/workspace/models"))
        self.assertEqual(config.adapter_timeout_ms, 15000)
        self.assertTrue(config.audit_enabled)

    def test_alias_usage_emits_actionable_warnings(self) -> None:
        env = {
            "R_PATH": "/usr/bin/R",
            "MCP_MODEL_SEARCH_PATHS": "/models",
            "AUDIT_TRAIL_ENABLED": "true",
        }
        warnings = config_env_warnings(env)
        self.assertIn(
            "Using deprecated env var R_PATH; prefer ADAPTER_R_PATH. Support will be removed in v0.6.0.",
            warnings,
        )
        self.assertIn(
            "Using deprecated env var MCP_MODEL_SEARCH_PATHS; prefer ADAPTER_MODEL_PATHS. Support will be removed in v0.6.0.",
            warnings,
        )
        self.assertIn(
            "Using deprecated env var AUDIT_TRAIL_ENABLED; prefer AUDIT_ENABLED. Support will be removed in v0.6.0.",
            warnings,
        )

    def test_blank_service_version_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"SERVICE_VERSION": "   "}, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.service_version, AppConfig.model_fields["service_version"].default)

    def test_s3_endpoint_and_path_style_env_are_loaded(self) -> None:
        env = {
            "AUDIT_STORAGE_BACKEND": "s3",
            "AUDIT_S3_BUCKET": "pbpk-mcp-audit-smoke",
            "AUDIT_S3_ENDPOINT_URL": "http://minio:9000",
            "AUDIT_S3_FORCE_PATH_STYLE": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.audit_storage_backend, "s3")
        self.assertEqual(config.audit_s3_bucket, "pbpk-mcp-audit-smoke")
        self.assertEqual(config.audit_s3_endpoint_url, "http://minio:9000")
        self.assertTrue(config.audit_s3_force_path_style)

    def test_mcp_transport_hardening_env_is_loaded(self) -> None:
        env = {
            "MCP_ALLOWED_ORIGINS": "https://agent.example, http://localhost:3000 ",
            "MCP_STRICT_TRANSPORT": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(
            config.mcp_allowed_origins,
            ("https://agent.example", "http://localhost:3000"),
        )
        self.assertTrue(config.mcp_strict_transport)


if __name__ == "__main__":
    unittest.main()
