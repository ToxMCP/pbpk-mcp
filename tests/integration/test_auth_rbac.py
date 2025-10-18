"""Integration tests covering authentication and RBAC enforcement."""

from __future__ import annotations

import tempfile

from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.security.simple_jwt import jwt


DEV_SECRET = "test-secret"


def _make_client() -> TestClient:
    audit_dir = tempfile.mkdtemp(prefix="audit-test-")
    config = AppConfig(auth_dev_secret=DEV_SECRET, audit_storage_path=audit_dir, audit_enabled=True)
    app = create_app(config=config)
    return TestClient(app)


def _encode_token(subject: str, roles: list[str]) -> str:
    payload = {"sub": subject, "roles": roles}
    return jwt.encode(payload, DEV_SECRET, algorithm="HS256")


def test_missing_token_returns_401() -> None:
    client = _make_client()
    response = client.post("/list_parameters", json={"simulationId": "sim", "searchPattern": "*"})
    assert response.status_code == 401


def test_viewer_token_allows_read_but_blocks_mutation() -> None:
    client = _make_client()
    viewer_token = _encode_token("viewer-user", ["viewer"])
    headers = {"Authorization": f"Bearer {viewer_token}"}

    read_resp = client.post(
        "/list_parameters",
        json={"simulationId": "sim", "searchPattern": "*"},
        headers=headers,
    )
    # simulation not loaded -> 404, but authorization succeeded
    assert read_resp.status_code in {404, 400}

    mutate_resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim",
            "parameterPath": "Organism|Weight",
            "value": 70.0,
        },
        headers=headers,
    )
    assert mutate_resp.status_code == 403


def test_operator_token_allows_mutation_flow() -> None:
    client = _make_client()
    operator_token = _encode_token("operator-user", ["operator"])
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Without loading a simulation this returns 404, validating we passed auth.
    mutate_resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim",
            "parameterPath": "Organism|Weight",
            "value": 70.0,
        },
        headers=headers,
    )
    assert mutate_resp.status_code in {404, 400}


def test_tampered_token_returns_401() -> None:
    client = _make_client()
    token = _encode_token("operator-user", ["operator"])
    tampered = token[:-2] + "ab"
    headers = {"Authorization": f"Bearer {tampered}"}

    resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim",
            "parameterPath": "Organism|Weight",
            "value": 70.0,
        },
        headers=headers,
    )
    assert resp.status_code == 401
