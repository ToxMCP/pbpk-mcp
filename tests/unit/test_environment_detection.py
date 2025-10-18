"""Tests for R environment detection utilities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from mcp_bridge.adapter.environment import detect_environment
from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.interface import AdapterConfig
from mcp_bridge.adapter.mock import InMemoryAdapter


def test_environment_detection_missing_r(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("R_PATH", raising=False)
    monkeypatch.delenv("R_HOME", raising=False)
    monkeypatch.delenv("OSPSUITE_LIBS", raising=False)

    with mock.patch("shutil.which", return_value=None):
        status = detect_environment(AdapterConfig())

    assert status.available is False
    assert any("R binary" in issue for issue in status.issues)


def test_environment_detection_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSPSUITE_LIBS", "/opt/ospsuite")

    with mock.patch("shutil.which", return_value="/usr/bin/R"):
        with mock.patch("os.path.exists", return_value=True):
            completed = SimpleNamespace(returncode=0, stdout="R version 4.3.2", stderr="")
            with mock.patch("subprocess.run", return_value=completed):
                status = detect_environment(AdapterConfig(default_timeout_seconds=1))

    assert status.available is True
    assert status.r_version == "R version 4.3.2"
    assert not status.issues


def test_adapter_requires_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("R_PATH", raising=False)
    monkeypatch.delenv("R_HOME", raising=False)
    with mock.patch("shutil.which", return_value=None):
        adapter = InMemoryAdapter(AdapterConfig(require_r_environment=True))
        with pytest.raises(AdapterError) as exc_info:
            adapter.init()

    assert exc_info.value.code == AdapterErrorCode.ENVIRONMENT_MISSING
