from __future__ import annotations

import time

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


def _post_call_tool(client: TestClient, payload: dict) -> dict:
    response = client.post("/mcp/call_tool", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_run_simulation_idempotency_deduplicates_jobs(tmp_path):
    config = AppConfig(job_registry_path=str(tmp_path / "jobs.db"), auth_allow_anonymous=True)
    app = create_app(config=config)

    with TestClient(app) as client:
        load_payload = {
            "tool": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "idempo-sim",
            },
            "critical": True,
        }
        _post_call_tool(client, load_payload)

        run_payload = {
            "tool": "run_simulation",
            "idempotencyKey": "idem-key-1",
            "arguments": {
                "simulationId": "idempo-sim",
                "runId": "idem-run",
            },
            "critical": True,
        }

        result1 = _post_call_tool(client, run_payload)
        result2 = _post_call_tool(client, run_payload)
        result3 = _post_call_tool(client, run_payload)

        job_id = result1["structuredContent"]["jobId"]
        assert result2["structuredContent"]["jobId"] == job_id
        assert result3["structuredContent"]["jobId"] == job_id

        job_service = app.state.jobs
        job = job_service.wait_for_completion(job_id, timeout=5.0)
        assert job.attempts == 1
        assert job.idempotency_key == "idem-key-1"


def test_run_simulation_idempotency_conflict(tmp_path):
    config = AppConfig(job_registry_path=str(tmp_path / "jobs.db"), auth_allow_anonymous=True)
    app = create_app(config=config)

    with TestClient(app) as client:
        load_payload = {
            "tool": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "idempo-conflict",
            },
            "critical": True,
        }
        _post_call_tool(client, load_payload)

        base_payload = {
            "tool": "run_simulation",
            "idempotencyKey": "idem-key-conflict",
            "arguments": {
                "simulationId": "idempo-conflict",
                "runId": "idem-run",
            },
            "critical": True,
        }
        _post_call_tool(client, base_payload)

        conflict_payload = {
            "tool": "run_simulation",
            "idempotencyKey": "idem-key-conflict",
            "arguments": {
                "simulationId": "idempo-conflict",
                "runId": "idem-run-different",
            },
            "critical": True,
        }
        response = client.post(
            "/mcp/call_tool",
            json=conflict_payload,
        )
        assert response.status_code == 409
        assert "Idempotency" in response.json()["error"]["message"]
