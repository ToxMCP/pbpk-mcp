"""Analyst console routes for reviewing literature extraction suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from mcp.tools.set_parameter_value import (
    SetParameterValueRequest as ToolSetParameterValueRequest,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueValidationError,
)
from mcp.tools.set_parameter_value import (
    set_parameter_value as execute_set_parameter_value,
)

from ..adapter import AdapterError
from ..literature.actions import LiteratureActionMapper
from ..literature.models import ActionSuggestion, LiteratureExtractionResult
from ..literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies
from ..literature.extractors import (
    HeuristicTextExtractor,
    PdfExtractKitLayoutExtractor,
    SimpleFigureExtractor,
    SimpleTableExtractor,
)
from ..dependencies import (
    get_adapter,
    get_audit_trail,
    get_job_service,
    should_offload_adapter,
)
from ..audit import AuditTrail
from ..errors import adapter_error_to_http
from ..services.job_service import BaseJobService
from ..adapter import OspsuiteAdapter
from ..util.concurrency import maybe_to_thread


router = APIRouter(prefix="/console/api", tags=["console"])

GOLDSET_ROOT = Path(__file__).resolve().parents[3] / "reference" / "goldset"
GOLDSET_MANIFEST = GOLDSET_ROOT / "index.json"


class SuggestionRequest(BaseModel):
    simulationId: str
    extraction: LiteratureExtractionResult


class SuggestionResponse(BaseModel):
    simulationId: str
    suggestions: List[ActionSuggestion]
    extraction: LiteratureExtractionResult


class DecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    suggestion: ActionSuggestion
    simulationId: Optional[str] = None


def _run_action_mapper(simulation_id: str, extraction: LiteratureExtractionResult) -> SuggestionResponse:
    mapper = LiteratureActionMapper(simulation_id=simulation_id)
    suggestions = mapper.map_actions(extraction)
    return SuggestionResponse(simulationId=simulation_id, suggestions=suggestions, extraction=extraction)


@router.post("/suggestions", response_model=SuggestionResponse)
async def generate_suggestions(payload: SuggestionRequest) -> SuggestionResponse:
    return _run_action_mapper(payload.simulationId, payload.extraction)


def _load_manifest() -> dict[str, Any]:
    if not GOLDSET_MANIFEST.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gold-set manifest not found. Run scripts/build_goldset.py to generate sample data.",
        )
    try:
        return json.loads(GOLDSET_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse gold-set manifest: {exc}",
        ) from exc


def _create_pipeline() -> LiteratureIngestionPipeline:
    deps = PipelineDependencies(
        layout_extractor=PdfExtractKitLayoutExtractor(),
        text_extractor=HeuristicTextExtractor(),
        table_extractor=SimpleTableExtractor(),
        figure_extractor=SimpleFigureExtractor(),
    )
    return LiteratureIngestionPipeline(deps)


@router.get("/samples")
def list_samples() -> dict[str, Any]:
    manifest = _load_manifest()
    return {
        "entries": [
            {
                "sourceId": entry["sourceId"],
                "label": entry["sourceId"],
            }
            for entry in manifest.get("entries", [])
        ]
    }


@router.get("/samples/{source_id}/suggestions", response_model=SuggestionResponse)
async def sample_suggestions(
    source_id: str,
    simulation_id: str = Query("sample-sim", alias="simulationId"),
) -> SuggestionResponse:
    manifest = _load_manifest()
    entry = next((item for item in manifest.get("entries", []) if item.get("sourceId") == source_id), None)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sample {source_id} not found")

    pdf_path = GOLDSET_ROOT / entry["pdf"]
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample PDF missing: {pdf_path}",
        )

    pipeline = _create_pipeline()
    extraction = pipeline.run(str(pdf_path), source_id=source_id)
    return _run_action_mapper(simulation_id, extraction)


@router.post("/decisions")
async def record_decision(
    payload: DecisionRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: BaseJobService = Depends(get_job_service),
    audit: AuditTrail = Depends(get_audit_trail),
) -> JSONResponse:
    suggestion = payload.suggestion
    simulation_id = payload.simulationId or suggestion.args.get("simulationId")
    if simulation_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="simulationId must be provided either explicitly or via suggestion args.",
        )

    if payload.decision == "rejected":
        audit.record_event(
            "console.suggestion.rejected",
            {"suggestion": suggestion.model_dump(mode="json"), "simulationId": simulation_id},
        )
        return JSONResponse({"status": "rejected"})

    if suggestion.tool_name != "set_parameter_value":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported tool '{suggestion.tool_name}' for analyst console.",
        )

    try:
        tool_payload = ToolSetParameterValueRequest.model_validate(suggestion.args)
    except ValidationError as exc:  # pragma: no cover - validation guard
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        response = await maybe_to_thread(
            should_offload_adapter(request),
            execute_set_parameter_value,
            adapter,
            tool_payload,
        )
    except SetParameterValueValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    audit.record_event(
        "console.suggestion.accepted",
        {
            "suggestion": suggestion.model_dump(mode="json"),
            "simulationId": simulation_id,
            "result": response.parameter.model_dump(mode="json"),
        },
    )
    return JSONResponse(
        {
            "status": "applied",
            "parameter": response.parameter.model_dump(mode="json"),
        }
    )
