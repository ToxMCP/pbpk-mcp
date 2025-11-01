"""Security-focused authentication tests."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.security.simple_jwt import jwt


DEV_SECRET = "security-secret"


def _make_config(tmp_path, **overrides) -> AppConfig:
    base = {
        "auth_dev_secret": DEV_SECRET,
        "audit_enabled": False,
        "audit_storage_path": str(tmp_path / "audit"),
        "population_storage_path": str(tmp_path / "population"),
        "snapshot_storage_path": str(tmp_path / "snapshots"),
        "auth_allow_anonymous": False,
        "auth_clock_skew_seconds": 0,
    }
    base.update(overrides)
    config = AppConfig(**base)
    assert config.auth_dev_secret == DEV_SECRET
    assert config.auth_allow_anonymous is False
    # Reset security caches to isolate between tests.
    from mcp_bridge.security import auth as auth_module

    with auth_module._RATE_LIMIT_LOCK:  # type: ignore[attr-defined]
        auth_module._RATE_LIMIT_CACHE.clear()
    with auth_module._TOKEN_CACHE_LOCK:  # type: ignore[attr-defined]
        auth_module._TOKEN_REPLAY_CACHE.clear()
    return config


def _encode_token(
    subject: str,
    roles: list[str],
    *,
    exp_offset: int = 300,
    jti: str | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": now,
        "exp": now + exp_offset,
    }
    payload["jti"] = jti or f"{subject}-{uuid.uuid4()}"
    return jwt.encode(payload, DEV_SECRET, algorithm="HS256")


def test_expired_token_rejected(tmp_path) -> None:
    config = _make_config(tmp_path)
    client = TestClient(create_app(config=config))
    expired_token = _encode_token("expired", ["viewer"], exp_offset=-30)

    response = client.get(
        "/mcp/list_tools",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_token_replay_detected(tmp_path) -> None:
    config = _make_config(tmp_path)
    client = TestClient(create_app(config=config))
    replay_token = _encode_token("replay", ["viewer"], jti="replay-token")

    first = client.get(
        "/mcp/list_tools",
        headers={"Authorization": f"Bearer {replay_token}"},
    )
    assert first.status_code == 200

    second = client.get(
        "/mcp/list_tools",
        headers={"Authorization": f"Bearer {replay_token}"},
    )
    assert second.status_code == 401


def test_rate_limit_enforced(tmp_path) -> None:
    config = _make_config(tmp_path, auth_rate_limit_per_minute=2)
    client = TestClient(create_app(config=config))

    headers = lambda: {"Authorization": f"Bearer {_encode_token('rate', ['viewer'])}"}

    assert client.get("/mcp/list_tools", headers=headers()).status_code == 200
    assert client.get("/mcp/list_tools", headers=headers()).status_code == 200
    third = client.get("/mcp/list_tools", headers=headers())
    assert third.status_code == 429
