from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


def test_metrics_endpoint_exposes_prometheus_series(tmp_path):
    config = AppConfig(
        audit_storage_path=str(tmp_path / "audit"),
        population_storage_path=str(tmp_path / "population"),
        job_registry_path=str(tmp_path / "jobs" / "registry.json"),
        auth_allow_anonymous=True,
    )

    app = create_app(config=config)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        # Exercise a tool call so tool-level metrics are emitted.
        payload = {
            "tool": "load_simulation",
            "arguments": {
                "filePath": str(Path("tests/fixtures/demo.pkml").resolve()),
                "simulationId": "metrics-test",
            },
            "critical": True,
        }
        tool_response = client.post(
            "/mcp/call_tool",
            json=payload,
        )
        assert tool_response.status_code == 200

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert metrics.headers["content-type"].startswith("text/plain")

        body = metrics.text
        assert "mcp_http_requests_total" in body
        assert "mcp_http_request_duration_seconds_bucket" in body
        assert "mcp_tool_invocations_total" in body
        assert "mcp_tool_duration_seconds_bucket" in body
