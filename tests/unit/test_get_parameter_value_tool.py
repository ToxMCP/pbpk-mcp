from __future__ import annotations

import pytest

from mcp.session_registry import registry
from mcp.tools.get_parameter_value import (
    GetParameterValueRequest,
    GetParameterValueResponse,
    GetParameterValueValidationError,
    get_parameter_value,
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
    instance.set_parameter_value("demo", "Organ.Liver.Weight", 2.0, unit="kg")
    return instance


def test_get_parameter_value_returns_payload(adapter: InMemoryAdapter) -> None:
    payload = GetParameterValueRequest(simulationId="demo", parameterPath="Organ.Liver.Weight")
    response = get_parameter_value(adapter, payload)
    assert isinstance(response, GetParameterValueResponse)
    assert response.parameter.value == 2.0
    assert response.parameter.unit == "kg"


def test_get_parameter_value_unknown_simulation(adapter: InMemoryAdapter) -> None:
    payload = GetParameterValueRequest(simulationId="missing", parameterPath="Organ.Liver.Weight")
    with pytest.raises(GetParameterValueValidationError):
        get_parameter_value(adapter, payload)


def test_get_parameter_value_invalid_path(adapter: InMemoryAdapter) -> None:
    with pytest.raises(ValueError):
        GetParameterValueRequest(simulationId="demo", parameterPath="\n")
