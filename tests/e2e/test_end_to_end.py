from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


REFERENCE_MODEL = Path("reference/models/standard/midazolam_adult.pkml")
EXPECTED_METRICS = {
    "cmax": 1.0,
    "tmax": 1.0,
    "auc": 0.5,
}
TOLERANCE_PERCENT = 1.0


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 30.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.post("/get_job_status", json={"jobId": job_id})
        assert response.status_code == 200, response.text
        payload = response.json()
        status = payload["status"].lower()
        if status in {"succeeded", "failed", "cancelled", "timeout"}:
            assert status == "succeeded", f"job ended with status {status!r}: {payload}"
            result_handle = payload.get("resultHandle") or {}
            result_id = result_handle.get("resultsId")
            assert result_id, "job succeeded but no resultId returned"
            return result_id
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not complete within {timeout} seconds")


def _percent_delta(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / expected * 100.0


@pytest.mark.e2e
def test_end_to_end_reference_midazolam(tmp_path):
    if not REFERENCE_MODEL.exists():
        pytest.skip("Reference model missing. Run `make fetch-bench-data`.")

    config = AppConfig(
        adapter_backend="inmemory",
        adapter_model_paths=(str(REFERENCE_MODEL.parent),),
        job_registry_path=str(tmp_path / "jobs.db"),
        population_storage_path=str(tmp_path / "population"),
        audit_storage_path=str(tmp_path / "audit"),
        auth_allow_anonymous=True,
    )

    app = create_app(config=config)
    simulation_id = "e2e-midazolam"

    artefact_dir = Path("reports/e2e")
    artefact_dir.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as client:
        # Load reference simulation
        resp = client.post(
            "/load_simulation",
            json={
                "filePath": str(REFERENCE_MODEL),
                "simulationId": simulation_id,
                "confirm": True,
            },
        )
        assert resp.status_code == 201, resp.text

        # Set a parameter to a known value
        resp = client.post(
            "/set_parameter_value",
            json={
                "simulationId": simulation_id,
                "parameterPath": "Organism|Weight",
                "value": 70.0,
                "unit": "kg",
                "comment": "E2E regression adjustment",
                "confirm": True,
            },
        )
        assert resp.status_code == 200, resp.text

        # Run simulation
        resp = client.post(
            "/run_simulation",
            json={
                "simulationId": simulation_id,
                "runId": "e2e-run",
                "confirm": True,
            },
        )
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["jobId"]

        result_id = _wait_for_job(client, job_id)

        # Fetch results for completeness
        resp = client.post("/get_simulation_results", json={"resultsId": result_id})
        assert resp.status_code == 200, resp.text
        results_payload = resp.json()

        # Calculate PK metrics and check parity tolerance
        resp = client.post("/calculate_pk_parameters", json={"resultsId": result_id})
        assert resp.status_code == 200, resp.text
        pk_payload = resp.json()

        metrics = pk_payload.get("metrics", [])
        assert metrics, "PK metrics payload empty"
        concentration = metrics[0]
        deltas = {
            key: _percent_delta(float(concentration[key]), EXPECTED_METRICS[key])
            for key in EXPECTED_METRICS
        }
        for metric, delta in deltas.items():
            assert delta <= TOLERANCE_PERCENT, (
                f"{metric} deviates {delta:.4f}% (allowed {TOLERANCE_PERCENT}%)"
            )

        artefact_path = artefact_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-midazolam.json"
        artefact = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulationId": simulation_id,
            "jobId": job_id,
            "resultId": result_id,
            "expectedMetrics": EXPECTED_METRICS,
            "actualMetrics": concentration,
            "deltaPercent": deltas,
            "sampleSeries": results_payload.get("series", []),
        }
        artefact_path.write_text(json.dumps(artefact, indent=2), encoding="utf-8")
