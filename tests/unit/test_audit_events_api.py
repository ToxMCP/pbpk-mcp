from __future__ import annotations

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


def test_list_audit_events_returns_tool_entries(tmp_path):
    config = AppConfig(
        audit_storage_path=str(tmp_path / "audit"),
        job_registry_path=str(tmp_path / "jobs.db"),
        auth_allow_anonymous=True,
    )
    app = create_app(config=config)

    with TestClient(app) as client:
        payload = {
            "tool": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "audit-sim",
            },
            "critical": True,
        }
        client.post("/mcp/call_tool", json=payload)

        run_payload = {
            "tool": "run_simulation",
            "idempotencyKey": "audit-key",
            "arguments": {
                "simulationId": "audit-sim",
                "runId": "audit-run",
            },
            "critical": True,
        }
        client.post("/mcp/call_tool", json=run_payload)

        response = client.get("/audit/events", params={"limit": 10})
        assert response.status_code == 200
        events = response.json()["events"]
        assert any(event["eventType"] == "tool.run_simulation" for event in events)
