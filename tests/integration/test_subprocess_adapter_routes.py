"""Integration coverage for the subprocess-backed adapter within FastAPI routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from mcp_bridge.adapter import AdapterConfig, AdapterError, AdapterErrorCode
from mcp_bridge.adapter.environment import REnvironmentStatus
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.adapter.ospsuite import CommandResult, SubprocessOspsuiteAdapter
from mcp_bridge.app import create_app

DEFAULT_PARAMS = {
    "Organ.Liver.Volume": {"value": 1.6, "unit": "L", "displayName": "Liver Volume"},
    "Protein.Plasma.Albumin": {"value": 45.0, "unit": "g/L", "displayName": "Albumin"},
}

# Allow opt-in when the real R toolchain is available.
_RUNS_R = os.getenv("MCP_RUN_R_TESTS", "0") == "1"
pytestmark = pytest.mark.skipif(not _RUNS_R, reason="R-dependent tests disabled")


def _fake_env_detector(_: AdapterConfig) -> REnvironmentStatus:
    return REnvironmentStatus(
        available=True,
        r_path="/usr/bin/R",
        ospsuite_libs="/opt/ospsuite",
        r_version="4.3.2",
        ospsuite_available=True,
        issues=[],
    )


class FakeBridgeRunner:
    """Command runner that proxies to the in-memory adapter for deterministic behaviour."""

    def __init__(self) -> None:
        self._adapter = InMemoryAdapter()
        self._adapter.init()
        self._expected_units: dict[str, str] = {
            path: meta["unit"] for path, meta in DEFAULT_PARAMS.items()
        }

    def __call__(self, action: str, payload: Mapping[str, Any]) -> CommandResult:
        try:
            if action == "load_simulation":
                handle = self._adapter.load_simulation(
                    payload["filePath"], simulation_id=payload["simulationId"]
                )
                params = []
                for path, details in DEFAULT_PARAMS.items():
                    value = self._adapter.set_parameter_value(
                        handle.simulation_id,
                        path,
                        details["value"],
                        unit=details["unit"],
                        comment=details["displayName"],
                    )
                    params.append(value.model_dump())
                body = {
                    "handle": handle.model_dump(),
                    "parameters": params,
                    "metadata": {"parameterCount": len(params)},
                }
            elif action == "list_parameters":
                params = self._adapter.list_parameters(
                    payload["simulationId"], payload.get("pattern")
                )
                body = {"parameters": [item.model_dump() for item in params]}
            elif action == "get_parameter_value":
                value = self._adapter.get_parameter_value(
                    payload["simulationId"], payload["parameterPath"]
                )
                body = {"parameter": value.model_dump()}
            elif action == "set_parameter_value":
                expected_unit = self._expected_units.get(payload["parameterPath"])
                supplied_unit = payload.get("unit")
                if expected_unit and supplied_unit and supplied_unit != expected_unit:
                    raise AdapterError(
                        AdapterErrorCode.INVALID_INPUT,
                        f"Unit mismatch for '{payload['parameterPath']}'",
                    )
                value = self._adapter.set_parameter_value(
                    payload["simulationId"],
                    payload["parameterPath"],
                    payload["value"],
                    unit=supplied_unit,
                    comment=payload.get("comment"),
                )
                body = {"parameter": value.model_dump()}
            elif action == "run_simulation_sync":
                result = self._adapter.run_simulation_sync(
                    payload["simulationId"], run_id=payload.get("runId")
                )
                if result.series:
                    result.series[0].values = [
                        {"time": float(index), "value": float(index)} for index in range(0, 120)
                    ]
                body = {"result": result.model_dump()}
            elif action == "get_results":
                result = self._adapter.get_results(payload["resultsId"])
                body = {"result": result.model_dump()}
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unknown action '{action}'")
            return CommandResult(returncode=0, stdout=json.dumps(body))
        except AdapterError as exc:
            return CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "error": {
                            "code": exc.code.value,
                            "message": exc.args[0],
                            "details": exc.details,
                        }
                    }
                ),
            )


class ExplodingRunner:
    """Runner that simulates hard failures to exercise error mapping."""

    def __call__(self, _: str, __: Mapping[str, Any]) -> CommandResult:
        return CommandResult(returncode=1, stdout="", stderr="boom")


@pytest.fixture()
def adapter_client(tmp_path: Path) -> tuple[TestClient, Path, SubprocessOspsuiteAdapter]:
    app = create_app()
    runner = FakeBridgeRunner()
    previous_paths = os.environ.get("MCP_MODEL_SEARCH_PATHS")
    os.environ["MCP_MODEL_SEARCH_PATHS"] = str(tmp_path)
    adapter = SubprocessOspsuiteAdapter(
        AdapterConfig(model_search_paths=(str(tmp_path),)),
        command_runner=runner,
        env_detector=_fake_env_detector,
    )
    adapter.init()
    app.state.adapter = adapter

    pkml = tmp_path / "integration-demo.pkml"
    pkml.write_text("<pkml/>", encoding="utf-8")

    # Debug assertion to ensure generated model path resides within allowed roots.
    assert any(pkml.resolve().is_relative_to(root) for root in adapter._allowed_roots)

    client = TestClient(app)
    try:
        yield client, pkml, adapter
    finally:
        if previous_paths is None:
            os.environ.pop("MCP_MODEL_SEARCH_PATHS", None)
        else:
            os.environ["MCP_MODEL_SEARCH_PATHS"] = previous_paths
        client.close()
        adapter.shutdown()
        try:
            from mcp.session_registry import registry

            registry.clear()
        except Exception:  # pragma: no cover - defensive cleanup
            pass


def test_missing_file_logs_redacted_message(
    adapter_client: tuple[TestClient, Path, SubprocessOspsuiteAdapter], tmp_path: Path
) -> None:
    client, pkml, _ = adapter_client
    missing = pkml.parent / "missing.pkml"
    request_path = f"{missing}?token=supersecret"

    with capture_logs() as logs:
        response = client.post(
            "/load_simulation",
            json={"filePath": request_path, "simulationId": "missing"},
        )

    assert response.status_code == 400
    error_logs = [entry for entry in logs if entry["event"] == "http.error"]
    assert error_logs
    log_entry = error_logs[0]
    assert "correlationId" in log_entry
    assert "supersecret" not in log_entry["message"]
    assert "token=" not in log_entry["message"]
    assert str(tmp_path) not in log_entry["message"]


def test_invalid_parameter_logs_context(
    adapter_client: tuple[TestClient, Path, SubprocessOspsuiteAdapter]
) -> None:
    client, pkml, adapter = adapter_client
    assert any(pkml.resolve().is_relative_to(root) for root in adapter._allowed_roots)
    assert adapter._resolve_model_path(str(pkml)).endswith(pkml.name)
    simulation_id = "demo-param"
    assert (
        client.post(
            "/load_simulation", json={"filePath": str(pkml), "simulationId": simulation_id}
        ).status_code
        == 201
    )

    with capture_logs() as logs:
        response = client.post(
            "/get_parameter_value",
            json={"simulationId": simulation_id, "parameterPath": "Unknown.Path"},
        )

    assert response.status_code == 404
    error_logs = [entry for entry in logs if entry["event"] == "http.error"]
    assert error_logs
    assert error_logs[0]["status_code"] == 404
    assert "correlationId" in error_logs[0]


def test_unit_mismatch_returns_bad_request(
    adapter_client: tuple[TestClient, Path, SubprocessOspsuiteAdapter]
) -> None:
    client, pkml, _ = adapter_client
    simulation_id = "demo-unit"
    assert (
        client.post(
            "/load_simulation", json={"filePath": str(pkml), "simulationId": simulation_id}
        ).status_code
        == 201
    )

    with capture_logs():
        response = client.post(
            "/set_parameter_value",
            json={
                "simulationId": simulation_id,
                "parameterPath": "Organ.Liver.Volume",
                "value": 2.0,
                "unit": "mg",
            },
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "InvalidInput"


def test_large_result_payload(
    adapter_client: tuple[TestClient, Path, SubprocessOspsuiteAdapter]
) -> None:
    client, pkml, _ = adapter_client
    simulation_id = "demo-results"
    assert (
        client.post(
            "/load_simulation", json={"filePath": str(pkml), "simulationId": simulation_id}
        ).status_code
        == 201
    )

    run_resp = client.post("/run_simulation", json={"simulationId": simulation_id})
    assert run_resp.status_code == 202
    job_id = run_resp.json()["jobId"]

    status_resp = client.post("/get_job_status", json={"jobId": job_id})
    assert status_resp.status_code == 200
    results_id = status_resp.json()["resultHandle"]["resultsId"]

    results_resp = client.post("/get_simulation_results", json={"resultsId": results_id})
    assert results_resp.status_code == 200
    results_payload = results_resp.json()
    assert results_payload["resultsId"] == results_id
    assert results_payload["series"]
    assert len(results_payload["series"][0]["values"]) >= 100
