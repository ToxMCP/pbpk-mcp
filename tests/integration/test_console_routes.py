from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


REFERENCE_MODELS = Path("reference/models/standard")


def _client(tmp_path: Path) -> TestClient:
    config = AppConfig(
        adapter_backend="inmemory",
        adapter_model_paths=(str(REFERENCE_MODELS.resolve()),),
        job_registry_path=str(tmp_path / "jobs.db"),
        population_storage_path=str(tmp_path / "population"),
        audit_storage_path=str(tmp_path / "audit"),
    )
    app = create_app(config=config)
    return TestClient(app)


def test_samples_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/console/api/samples")
    assert response.status_code == 200
    payload = response.json()
    assert "entries" in payload
    assert len(payload["entries"]) >= 1


def test_sample_suggestions_and_apply(tmp_path: Path) -> None:
    client = _client(tmp_path)

    # Load sample simulation so accepted suggestions can be applied.
    model_path = REFERENCE_MODELS / "midazolam_adult.pkml"
    load_resp = client.post(
        "/load_simulation",
        json={
            "filePath": str(model_path),
            "simulationId": "console-test-sim",
        },
    )
    assert load_resp.status_code == 201

    suggestions_resp = client.get(
        "/console/api/samples/paper-001/suggestions",
        params={"simulationId": "console-test-sim"},
    )
    assert suggestions_resp.status_code == 200

    suggestions_payload = suggestions_resp.json()
    suggestions = suggestions_payload["suggestions"]
    assert suggestions, "Expected at least one suggestion from sample data"

    decision_resp = client.post(
        "/console/api/decisions",
        json={
            "decision": "accepted",
            "simulationId": "console-test-sim",
            "suggestion": suggestions[0],
        },
    )
    assert decision_resp.status_code == 200
    decision_payload = decision_resp.json()
    assert decision_payload["status"] == "applied"


def test_manual_suggestions_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path)
    suggestions_resp = client.get(
        "/console/api/samples/paper-002/suggestions",
        params={"simulationId": "manual-test-sim"},
    )
    assert suggestions_resp.status_code == 200
    sample_payload = suggestions_resp.json()

    manual_resp = client.post(
        "/console/api/suggestions",
        json={
            "simulationId": "manual-test-sim",
            "extraction": sample_payload["extraction"],
        },
    )
    assert manual_resp.status_code == 200
    manual_payload = manual_resp.json()
    assert manual_payload["simulationId"] == "manual-test-sim"
    assert len(manual_payload["suggestions"]) == len(sample_payload["suggestions"])
