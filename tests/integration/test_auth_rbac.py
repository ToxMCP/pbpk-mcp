"""Integration tests covering authentication and RBAC enforcement."""

from __future__ import annotations

import tempfile
import time
import uuid

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


def _encode_token(subject: str, roles: list[str], *, jti: str | None = None, exp_offset: int = 300) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": now,
        "exp": now + exp_offset,
    }
    if jti is None:
        jti = f"{subject}-{uuid.uuid4()}"
    payload["jti"] = jti
    return jwt.encode(payload, DEV_SECRET, algorithm="HS256")


def test_missing_token_returns_401() -> None:
    client = _make_client()
    response = client.post("/list_parameters", json={"simulationId": "sim", "searchPattern": "*"})
    assert response.status_code == 401


def test_viewer_token_allows_read_but_blocks_mutation() -> None:
    client = _make_client()
    read_headers = {"Authorization": f"Bearer {_encode_token('viewer-user', ['viewer'])}"}

    read_resp = client.post(
        "/list_parameters",
        json={"simulationId": "sim", "searchPattern": "*"},
        headers=read_headers,
    )
    # simulation not loaded -> 404, but authorization succeeded
    assert read_resp.status_code in {404, 400}

    mutate_headers = {"Authorization": f"Bearer {_encode_token('viewer-user', ['viewer'])}"}
    mutate_resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim",
            "parameterPath": "Organism|Weight",
            "value": 70.0,
            "confirm": True,
        },
        headers=mutate_headers,
    )
    assert mutate_resp.status_code == 403


def test_operator_token_allows_mutation_flow() -> None:
    client = _make_client()
    headers = {"Authorization": f"Bearer {_encode_token('operator-user', ['operator'])}"}

    # Without loading a simulation this returns 404, validating we passed auth.
    mutate_resp = client.post(
        "/set_parameter_value",
        json={
            "simulationId": "sim",
            "parameterPath": "Organism|Weight",
            "value": 70.0,
            "confirm": True,
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
            "confirm": True,
        },
        headers=headers,
    )
    assert resp.status_code == 401
