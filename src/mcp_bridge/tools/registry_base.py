"""Shared tool registry definitions for MCP Bridge."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Optional, Tuple, Type

from pydantic import BaseModel


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


def standard_roles(*roles: str) -> Tuple[str, ...]:
    return tuple(roles or ("viewer",))


@lru_cache(maxsize=1)
def _tool_components() -> Dict[str, Any]:
    from mcp.tools.calculate_pk_parameters import (
        CalculatePkParametersRequest,
        CalculatePkParametersResponse,
        calculate_pk_parameters,
    )
    from mcp.tools.cancel_job import CancelJobRequest, CancelJobResponse, cancel_job
    from mcp.tools.discover_models import DiscoverModelsRequest, DiscoverModelsResponse, discover_models
    from mcp.tools.export_oecd_report import ExportOecdReportRequest, ExportOecdReportResponse, export_oecd_report
    from mcp.tools.get_job_status import GetJobStatusRequest, GetJobStatusResponse, get_job_status
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
    from mcp.tools.get_results import GetResultsRequest, GetResultsResponse, get_results
    from mcp.tools.ingest_external_pbpk_bundle import (
        IngestExternalPbpkBundleRequest,
        IngestExternalPbpkBundleResponse,
        ingest_external_pbpk_bundle,
    )
    from mcp.tools.list_parameters import ListParametersRequest, ListParametersResponse, list_parameters
    from mcp.tools.load_simulation import LoadSimulationRequest, LoadSimulationResponse, load_simulation
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
    from mcp.tools.run_simulation import RunSimulationRequest, RunSimulationResponse, run_simulation
    from mcp.tools.run_verification_checks import (
        RunVerificationChecksRequest,
        RunVerificationChecksResponse,
        run_verification_checks,
    )
    from mcp.tools.set_parameter_value import (
        SetParameterValueRequest,
        SetParameterValueResponse,
        set_parameter_value,
    )
    from mcp.tools.validate_model_manifest import (
        ValidateModelManifestRequest,
        ValidateModelManifestResponse,
        validate_model_manifest,
    )
    from mcp.tools.validate_simulation_request import (
        ValidateSimulationRequestRequest,
        ValidateSimulationRequestResponse,
        validate_simulation_request,
    )

    return {
        "CalculatePkParametersRequest": CalculatePkParametersRequest,
        "CalculatePkParametersResponse": CalculatePkParametersResponse,
        "calculate_pk_parameters": calculate_pk_parameters,
        "CancelJobRequest": CancelJobRequest,
        "CancelJobResponse": CancelJobResponse,
        "cancel_job": cancel_job,
        "DiscoverModelsRequest": DiscoverModelsRequest,
        "DiscoverModelsResponse": DiscoverModelsResponse,
        "discover_models": discover_models,
        "ExportOecdReportRequest": ExportOecdReportRequest,
        "ExportOecdReportResponse": ExportOecdReportResponse,
        "export_oecd_report": export_oecd_report,
        "GetJobStatusRequest": GetJobStatusRequest,
        "GetJobStatusResponse": GetJobStatusResponse,
        "get_job_status": get_job_status,
        "GetParameterValueRequest": GetParameterValueRequest,
        "GetParameterValueResponse": GetParameterValueResponse,
        "get_parameter_value": get_parameter_value,
        "GetPopulationResultsRequest": GetPopulationResultsRequest,
        "GetPopulationResultsResponse": GetPopulationResultsResponse,
        "get_population_results": get_population_results,
        "GetResultsRequest": GetResultsRequest,
        "GetResultsResponse": GetResultsResponse,
        "get_results": get_results,
        "IngestExternalPbpkBundleRequest": IngestExternalPbpkBundleRequest,
        "IngestExternalPbpkBundleResponse": IngestExternalPbpkBundleResponse,
        "ingest_external_pbpk_bundle": ingest_external_pbpk_bundle,
        "ListParametersRequest": ListParametersRequest,
        "ListParametersResponse": ListParametersResponse,
        "list_parameters": list_parameters,
        "LoadSimulationRequest": LoadSimulationRequest,
        "LoadSimulationResponse": LoadSimulationResponse,
        "load_simulation": load_simulation,
        "RunPopulationSimulationRequest": RunPopulationSimulationRequest,
        "RunPopulationSimulationResponse": RunPopulationSimulationResponse,
        "run_population_simulation": run_population_simulation,
        "RunSensitivityAnalysisRequest": RunSensitivityAnalysisRequest,
        "RunSensitivityAnalysisResponse": RunSensitivityAnalysisResponse,
        "run_sensitivity_analysis_tool": run_sensitivity_analysis_tool,
        "RunSimulationRequest": RunSimulationRequest,
        "RunSimulationResponse": RunSimulationResponse,
        "run_simulation": run_simulation,
        "RunVerificationChecksRequest": RunVerificationChecksRequest,
        "RunVerificationChecksResponse": RunVerificationChecksResponse,
        "run_verification_checks": run_verification_checks,
        "SetParameterValueRequest": SetParameterValueRequest,
        "SetParameterValueResponse": SetParameterValueResponse,
        "set_parameter_value": set_parameter_value,
        "ValidateModelManifestRequest": ValidateModelManifestRequest,
        "ValidateModelManifestResponse": ValidateModelManifestResponse,
        "validate_model_manifest": validate_model_manifest,
        "ValidateSimulationRequestRequest": ValidateSimulationRequestRequest,
        "ValidateSimulationRequestResponse": ValidateSimulationRequestResponse,
        "validate_simulation_request": validate_simulation_request,
    }


def get_base_tool_registry(
    *,
    load_simulation_description: str | None = None,
) -> Dict[str, ToolDescriptor]:
    """Return the packaged base MCP tool registry keyed by tool name."""

    tools = _tool_components()

    return {
        "load_simulation": ToolDescriptor(
            name="load_simulation",
            description=load_simulation_description
            or "Load a PBPK model (.pkml or MCP-ready .R) into the active session registry.",
            request_model=tools["LoadSimulationRequest"],
            response_model=tools["LoadSimulationResponse"],
            handler=tools["load_simulation"],
            dependencies=("adapter",),
            roles=standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "discover_models": ToolDescriptor(
            name="discover_models",
            description="Discover supported PBPK model files under ADAPTER_MODEL_PATHS, including unloaded workspace models.",
            request_model=tools["DiscoverModelsRequest"],
            response_model=tools["DiscoverModelsResponse"],
            handler=tools["discover_models"],
            dependencies=(),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "list_parameters": ToolDescriptor(
            name="list_parameters",
            description="List parameter paths available in a loaded simulation (supports glob filters).",
            request_model=tools["ListParametersRequest"],
            response_model=tools["ListParametersResponse"],
            handler=tools["list_parameters"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "get_parameter_value": ToolDescriptor(
            name="get_parameter_value",
            description="Retrieve the current value for a simulation parameter.",
            request_model=tools["GetParameterValueRequest"],
            response_model=tools["GetParameterValueResponse"],
            handler=tools["get_parameter_value"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "set_parameter_value": ToolDescriptor(
            name="set_parameter_value",
            description="Update a parameter in the simulation with an optional unit and comment.",
            request_model=tools["SetParameterValueRequest"],
            response_model=tools["SetParameterValueResponse"],
            handler=tools["set_parameter_value"],
            dependencies=("adapter",),
            roles=standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "run_simulation": ToolDescriptor(
            name="run_simulation",
            description="Submit an asynchronous simulation job and receive a job handle.",
            request_model=tools["RunSimulationRequest"],
            response_model=tools["RunSimulationResponse"],
            handler=tools["run_simulation"],
            dependencies=("adapter", "job_service"),
            roles=standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "get_job_status": ToolDescriptor(
            name="get_job_status",
            description="Inspect the status of a previously submitted job.",
            request_model=tools["GetJobStatusRequest"],
            response_model=tools["GetJobStatusResponse"],
            handler=tools["get_job_status"],
            dependencies=("job_service",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "get_results": ToolDescriptor(
            name="get_results",
            description="Retrieve stored deterministic simulation results by handle.",
            request_model=tools["GetResultsRequest"],
            response_model=tools["GetResultsResponse"],
            handler=tools["get_results"],
            dependencies=("adapter", "job_service"),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "calculate_pk_parameters": ToolDescriptor(
            name="calculate_pk_parameters",
            description="Compute PK metrics (Cmax, Tmax, AUC) for an existing simulation results handle.",
            request_model=tools["CalculatePkParametersRequest"],
            response_model=tools["CalculatePkParametersResponse"],
            handler=tools["calculate_pk_parameters"],
            dependencies=("adapter", "job_service"),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "run_population_simulation": ToolDescriptor(
            name="run_population_simulation",
            description="Execute a population simulation asynchronously and return a job handle.",
            request_model=tools["RunPopulationSimulationRequest"],
            response_model=tools["RunPopulationSimulationResponse"],
            handler=tools["run_population_simulation"],
            dependencies=("adapter", "job_service"),
            roles=standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "validate_simulation_request": ToolDescriptor(
            name="validate_simulation_request",
            description="Run a preflight OECD-style applicability and guardrail assessment for a loaded model.",
            request_model=tools["ValidateSimulationRequestRequest"],
            response_model=tools["ValidateSimulationRequestResponse"],
            handler=tools["validate_simulation_request"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "validate_model_manifest": ToolDescriptor(
            name="validate_model_manifest",
            description="Run a static manifest check for a supported model file before loading it, including qualification-state and metadata coverage hints.",
            request_model=tools["ValidateModelManifestRequest"],
            response_model=tools["ValidateModelManifestResponse"],
            handler=tools["validate_model_manifest"],
            dependencies=(),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "run_verification_checks": ToolDescriptor(
            name="run_verification_checks",
            description="Run executable verification checks for a loaded model, including deterministic smoke tests and optional population smoke where supported.",
            request_model=tools["RunVerificationChecksRequest"],
            response_model=tools["RunVerificationChecksResponse"],
            handler=tools["run_verification_checks"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "get_population_results": ToolDescriptor(
            name="get_population_results",
            description="Fetch aggregated results and chunk handles for a completed population simulation.",
            request_model=tools["GetPopulationResultsRequest"],
            response_model=tools["GetPopulationResultsResponse"],
            handler=tools["get_population_results"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "cancel_job": ToolDescriptor(
            name="cancel_job",
            description="Request cancellation of a queued or running asynchronous job.",
            request_model=tools["CancelJobRequest"],
            response_model=tools["CancelJobResponse"],
            handler=tools["cancel_job"],
            dependencies=("job_service",),
            roles=standard_roles("operator", "admin"),
        ),
        "run_sensitivity_analysis": ToolDescriptor(
            name="run_sensitivity_analysis",
            description="Execute a multi-parameter sensitivity analysis workflow and return PK deltas.",
            request_model=tools["RunSensitivityAnalysisRequest"],
            response_model=tools["RunSensitivityAnalysisResponse"],
            handler=tools["run_sensitivity_analysis_tool"],
            dependencies=("adapter", "job_service"),
            roles=standard_roles("operator", "admin"),
            critical=True,
            requires_confirmation=True,
        ),
        "export_oecd_report": ToolDescriptor(
            name="export_oecd_report",
            description="Export an OECD-style model dossier/report for a loaded simulation, including profile, assessment, and parameter provenance.",
            request_model=tools["ExportOecdReportRequest"],
            response_model=tools["ExportOecdReportResponse"],
            handler=tools["export_oecd_report"],
            dependencies=("adapter",),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
        "ingest_external_pbpk_bundle": ToolDescriptor(
            name="ingest_external_pbpk_bundle",
            description="Normalize externally generated PBPK outputs, qualification metadata, and optional PoD references into PBPK-side NGRA-ready objects without executing the upstream engine.",
            request_model=tools["IngestExternalPbpkBundleRequest"],
            response_model=tools["IngestExternalPbpkBundleResponse"],
            handler=tools["ingest_external_pbpk_bundle"],
            dependencies=(),
            roles=standard_roles("viewer", "operator", "admin"),
        ),
    }


__all__ = ["ToolDescriptor", "get_base_tool_registry", "standard_roles"]
