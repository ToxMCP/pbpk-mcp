"""Basic contract tests for the ospsuite adapter interface."""

from __future__ import annotations

import pytest

from mcp_bridge.adapter import AdapterConfig, AdapterError, AdapterErrorCode
from mcp_bridge.adapter.mock import InMemoryAdapter


@pytest.fixture()
def adapter() -> InMemoryAdapter:
    instance = InMemoryAdapter(config=AdapterConfig())
    instance.init()
    yield instance
    instance.shutdown()


def test_load_simulation_returns_handle(adapter: InMemoryAdapter) -> None:
    handle = adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="sim-1")

    assert handle.simulation_id == "sim-1"
    assert handle.file_path.endswith("demo.pkml")


def test_get_and_set_parameter(adapter: InMemoryAdapter) -> None:
    adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="sim-2")
    updated = adapter.set_parameter_value("sim-2", "Organ.Liver.Weight", 1.23, unit="kg")

    assert updated.value == 1.23
    assert updated.unit == "kg"

    fetched = adapter.get_parameter_value("sim-2", "Organ.Liver.Weight")

    assert fetched.value == 1.23


def test_missing_simulation_errors(adapter: InMemoryAdapter) -> None:
    with pytest.raises(AdapterError) as exc_info:
        adapter.list_parameters("missing")

    assert exc_info.value.code == AdapterErrorCode.NOT_FOUND


def test_run_simulation_produces_results(adapter: InMemoryAdapter) -> None:
    adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="sim-3")

    result = adapter.run_simulation_sync("sim-3")

    assert result.simulation_id == "sim-3"
    assert result.series


def test_must_initialise_before_use() -> None:
    adapter = InMemoryAdapter()
    with pytest.raises(AdapterError) as exc_info:
        adapter.load_simulation("tests/fixtures/demo.pkml")

    assert exc_info.value.code == AdapterErrorCode.ENVIRONMENT_MISSING
