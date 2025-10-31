"""Configuration-level authentication assertions."""

from __future__ import annotations

import pytest

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig, ConfigError


def test_create_app_requires_oidc_in_production(tmp_path) -> None:
    config = AppConfig(
        environment="production",
        audit_enabled=False,
        audit_storage_path=str(tmp_path / "audit"),
        population_storage_path=str(tmp_path / "population"),
        snapshot_storage_path=str(tmp_path / "snapshots"),
    )
    with pytest.raises(ConfigError):
        create_app(config=config)
