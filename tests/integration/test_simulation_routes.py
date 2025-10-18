"""Integration tests for simulation routes."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app


def test_load_and_mutate_parameter_flow() -> None:
    client = TestClient(create_app())

    load_resp = client.post(
        "/load_simulation",
        json={"filePath": "tests/fixtures/demo.pkml", "simulationId": "sim-route"},
    )
    assert load_resp.status_code == 201
    load_payload = load_resp.json()
    assert load_payload["simulationId"] == "sim-route"

    set_resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim-route",
            "parameterPath": "Organ.Liver.Weight",
            "value": 2.5,
            "unit": "kg",
        },
    )
    assert set_resp.status_code == 200

    get_resp = client.post(
        "/get_parameter_value",
        json={
            "simulationId": "sim-route",
            "parameterPath": "Organ.Liver.Weight",
        },
    )
    payload = get_resp.json()
    assert get_resp.status_code == 200
    assert payload["parameter"]["value"] == 2.5

    run_resp = client.post(
        "/run_simulation",
        json={"simulationId": "sim-route"},
    )
    assert run_resp.status_code == 202
    job_id = run_resp.json()["jobId"]

    status_payload = _wait_for_job_completion(client, job_id)
    result_handle = status_payload.get("resultHandle")
    assert result_handle
    result_id = result_handle["resultsId"]

    results_resp = client.post("/get_simulation_results", json={"resultsId": result_id})
    assert results_resp.status_code == 200
    results_payload = results_resp.json()
    assert results_payload["resultsId"] == result_id
    assert results_payload["series"]

    pk_resp = client.post(
        "/calculate_pk_parameters",
        json={"resultsId": result_id},
    )
    assert pk_resp.status_code == 200
    pk_payload = pk_resp.json()
    assert pk_payload["resultsId"] == result_id
    assert pk_payload["metrics"]


def test_missing_simulation_returns_not_found() -> None:
    client = TestClient(create_app())

    resp = client.post(
        "/get_parameter_value",
        json={"simulationId": "missing", "parameterPath": "Path"},
    )
    assert resp.status_code == 404


def test_duplicate_simulation_returns_conflict() -> None:
    client = TestClient(create_app())
    payload = {"filePath": "tests/fixtures/demo.pkml", "simulationId": "dup-route"}
    assert client.post("/load_simulation", json=payload).status_code == 201
    resp = client.post("/load_simulation", json=payload)
    assert resp.status_code == 409


def test_invalid_extension_returns_bad_request() -> None:
    client = TestClient(create_app())
    resp = client.post(
        "/load_simulation",
        json={"filePath": "tests/fixtures/demo.txt", "simulationId": "bad-ext"},
    )
    assert resp.status_code == 400


def test_list_parameters_route() -> None:
    client = TestClient(create_app())
    load_payload = {"filePath": "tests/fixtures/demo.pkml", "simulationId": "sim-list"}
    assert client.post("/load_simulation", json=load_payload).status_code == 201

    client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim-list",
            "parameterPath": "Organ.Liver.Weight",
            "value": 2.0,
            "unit": "kg",
        },
    )
    resp = client.post(
        "/list_parameters",
        json={"simulationId": "sim-list", "searchPattern": "*"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload["parameters"], list)
    assert payload["parameters"]

    missing = client.post(
        "/list_parameters",
        json={"simulationId": "missing"},
    )
    assert missing.status_code == 404

    invalid = client.post(
        "/list_parameters",
        json={"simulationId": "sim-list", "searchPattern": "\n"},
    )
    assert invalid.status_code == 400


def test_population_simulation_endpoints() -> None:
    client = TestClient(create_app())

    payload = {
        "modelPath": "tests/fixtures/demo.pkml",
        "simulationId": "sim-pop",
        "cohort": {"size": 40, "sampling": "fixed"},
        "outputs": {"aggregates": ["mean", "sd"]},
    }

    run_resp = client.post("/run_population_simulation", json=payload)
    assert run_resp.status_code == 202
    job_id = run_resp.json()["jobId"]

    status_payload = _wait_for_job_completion(client, job_id, timeout=5.0)
    result_handle = status_payload.get("resultHandle") or {}
    results_id = result_handle.get("resultsId")
    assert results_id

    results_resp = client.post("/get_population_results", json={"resultsId": results_id})
    assert results_resp.status_code == 200
    results_payload = results_resp.json()
    assert results_payload["simulationId"] == "sim-pop"
    assert results_payload["aggregates"]
    assert results_payload["chunks"]
    chunk = results_payload["chunks"][0]
    assert chunk["uri"]
    chunk_resp = client.get(chunk["uri"])
    assert chunk_resp.status_code == 200
    assert chunk_resp.headers["content-type"].startswith("application/json")
    chunk_payload = chunk_resp.json()
    assert chunk_payload["chunkId"] == chunk["chunkId"]


def _wait_for_job_completion(client: TestClient, job_id: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict | None = None
    while time.time() < deadline:
        resp = client.post("/get_job_status", json={"jobId": job_id})
        assert resp.status_code == 200
        last_payload = resp.json()
        if last_payload["status"] not in {"queued", "running"}:
            return last_payload
        time.sleep(0.05)
    assert last_payload is not None
    return last_payload
