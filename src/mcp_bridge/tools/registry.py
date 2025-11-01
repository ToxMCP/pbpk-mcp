"""Central registry describing MCP tools exposed by the bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Type

from pydantic import BaseModel

from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersRequest,
    CalculatePkParametersResponse,
    calculate_pk_parameters,
)
from mcp.tools.cancel_job import (
    CancelJobRequest,
    CancelJobResponse,
    cancel_job,
)
from mcp.tools.get_job_status import (
    GetJobStatusRequest,
    GetJobStatusResponse,
    get_job_status,
)
from mcp.tools.get_parameter_value import (
    GetParameterValueRequest,
    GetParameterValueResponse,
    get_parameter_value,
)
from mcp.tools.get_population_results import (
    GetPopulationResultsRequest,
    GetPopulationResultsResponse,
    get_population_results,
)
from mcp.tools.list_parameters import (
    ListParametersRequest,
    ListParametersResponse,
    list_parameters,
)
from mcp.tools.load_simulation import (
    LoadSimulationRequest,
    LoadSimulationResponse,
    load_simulation,
)
from mcp.tools.run_population_simulation import (
    RunPopulationSimulationRequest,
    RunPopulationSimulationResponse,
    run_population_simulation,
)
from mcp.tools.run_sensitivity_analysis import (
    RunSensitivityAnalysisRequest,
    RunSensitivityAnalysisResponse,
    run_sensitivity_analysis_tool,
)
from mcp.tools.run_simulation import (
    RunSimulationRequest,
    RunSimulationResponse,
    run_simulation,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueRequest,
    SetParameterValueResponse,
    set_parameter_value,
)

DependencyName = str


@dataclass(frozen=True)
class ToolDescriptor:
    """Metadata describing a single MCP tool."""

    name: str
    description: str
    request_model: Type[BaseModel]
    response_model: Optional[Type[BaseModel]]
    handler: Callable[..., Any]
    dependencies: Tuple[DependencyName, ...]
    roles: Tuple[str, ...]
    critical: bool = False
    requires_confirmation: bool = False

    def input_schema(self) -> Dict[str, Any]:
        return self.request_model.model_json_schema()

    def output_schema(self) -> Optional[Dict[str, Any]]:
        if self.response_model is None:
            return None
        return self.response_model.model_json_schema()


def _standard_roles(*roles: str) -> Tuple[str, ...]:
    return tuple(roles or ("viewer",))


def get_tool_registry() -> Dict[str, ToolDescriptor]:
    """Return the MCP tool registry keyed by tool name."""

    return {
        "load_simulation": ToolDescriptor(
            name="load_simulation",
            description="Load a PBPK simulation (.pkml) into the active session registry.",
            request_model=LoadSimulationRequest,
            response_model=LoadSimulationResponse,
            handler=load_simulation,
            dependencies=("adapter",),
            roles=_standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "list_parameters": ToolDescriptor(
            name="list_parameters",
            description=(
                "List parameter paths available in a loaded simulation "
                "(supports glob filters)."
            ),
            request_model=ListParametersRequest,
            response_model=ListParametersResponse,
            handler=list_parameters,
            dependencies=("adapter",),
            roles=_standard_roles("viewer", "operator", "admin"),
        ),
        "get_parameter_value": ToolDescriptor(
            name="get_parameter_value",
            description="Retrieve the current value for a simulation parameter.",
            request_model=GetParameterValueRequest,
            response_model=GetParameterValueResponse,
            handler=get_parameter_value,
            dependencies=("adapter",),
            roles=_standard_roles("viewer", "operator", "admin"),
        ),
        "set_parameter_value": ToolDescriptor(
            name="set_parameter_value",
            description="Update a parameter in the simulation with an optional unit and comment.",
            request_model=SetParameterValueRequest,
            response_model=SetParameterValueResponse,
            handler=set_parameter_value,
            dependencies=("adapter",),
            roles=_standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "run_simulation": ToolDescriptor(
            name="run_simulation",
            description="Submit an asynchronous simulation job and receive a job handle.",
            request_model=RunSimulationRequest,
            response_model=RunSimulationResponse,
            handler=run_simulation,
            dependencies=("adapter", "job_service"),
            roles=_standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "get_job_status": ToolDescriptor(
            name="get_job_status",
            description="Inspect the status of a previously submitted job.",
            request_model=GetJobStatusRequest,
            response_model=GetJobStatusResponse,
            handler=get_job_status,
            dependencies=("job_service",),
            roles=_standard_roles("viewer", "operator", "admin"),
        ),
        "calculate_pk_parameters": ToolDescriptor(
            name="calculate_pk_parameters",
            description=(
                "Compute PK metrics (Cmax, Tmax, AUC) for an existing "
                "simulation results handle."
            ),
            request_model=CalculatePkParametersRequest,
            response_model=CalculatePkParametersResponse,
            handler=calculate_pk_parameters,
            dependencies=("adapter",),
            roles=_standard_roles("viewer", "operator", "admin"),
        ),
        "run_population_simulation": ToolDescriptor(
            name="run_population_simulation",
            description="Execute a population simulation asynchronously and return a job handle.",
            request_model=RunPopulationSimulationRequest,
            response_model=RunPopulationSimulationResponse,
            handler=run_population_simulation,
            dependencies=("adapter", "job_service"),
            roles=_standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "get_population_results": ToolDescriptor(
            name="get_population_results",
            description=(
                "Fetch aggregated results and chunk handles for a completed "
                "population simulation."
            ),
            request_model=GetPopulationResultsRequest,
            response_model=GetPopulationResultsResponse,
            handler=get_population_results,
            dependencies=("adapter",),
            roles=_standard_roles("viewer", "operator", "admin"),
        ),
        "cancel_job": ToolDescriptor(
            name="cancel_job",
            description="Request cancellation of a queued or running asynchronous job.",
            request_model=CancelJobRequest,
            response_model=CancelJobResponse,
            handler=cancel_job,
            dependencies=("job_service",),
            roles=_standard_roles("operator", "admin"),
        ),
        "run_sensitivity_analysis": ToolDescriptor(
            name="run_sensitivity_analysis",
            description=(
                "Execute a multi-parameter sensitivity analysis workflow "
                "and return PK deltas."
            ),
            request_model=RunSensitivityAnalysisRequest,
            response_model=RunSensitivityAnalysisResponse,
            handler=run_sensitivity_analysis_tool,
            dependencies=("adapter", "job_service"),
            roles=_standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
    }


__all__ = ["ToolDescriptor", "get_tool_registry"]
