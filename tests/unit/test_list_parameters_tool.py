from __future__ import annotations

import pytest

from mcp.session_registry import registry
from mcp.tools.list_parameters import (
    ListParametersRequest,
    ListParametersResponse,
    ListParametersValidationError,
    list_parameters,
)
from mcp_bridge.adapter.mock import InMemoryAdapter


@pytest.fixture(autouse=True)
def clear_registry() -> None:
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def adapter() -> InMemoryAdapter:
    instance = InMemoryAdapter()
    instance.init()
    handle = instance.load_simulation("tests/fixtures/demo.pkml", simulation_id="demo")
    registry.register(handle)
    instance.set_parameter_value("demo", "Organ.Liver.Weight", 1.0)
    return instance


def test_list_parameters_returns_paths(adapter: InMemoryAdapter) -> None:
    payload = ListParametersRequest(simulationId="demo", searchPattern="*")
    response = list_parameters(adapter, payload)
    assert isinstance(response, ListParametersResponse)
    assert response.parameters
    assert all(isinstance(item, str) for item in response.parameters)


def test_list_parameters_unknown_simulation(adapter: InMemoryAdapter) -> None:
    payload = ListParametersRequest(simulationId="unknown")
    with pytest.raises(ListParametersValidationError):
        list_parameters(adapter, payload)


def test_list_parameters_invalid_pattern(adapter: InMemoryAdapter) -> None:
    with pytest.raises(ValueError):
        ListParametersRequest(simulationId="demo", searchPattern="\n")
