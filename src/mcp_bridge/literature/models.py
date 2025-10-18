"""Data models for literature ingestion pipeline outputs."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    """Supported document component types."""

    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"


class BoundingBox(BaseModel):
    """Absolute bounding box in PDF coordinate space."""

    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(gt=0)
    y1: float = Field(gt=0)


class DocumentComponent(BaseModel):
    """Representation of a segmented PDF component."""

    component_id: str
    page: int = Field(ge=1)
    type: ComponentType
    bbox: BoundingBox
    text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedField(BaseModel):
    """Structured field extracted from a component."""

    name: str
    value: Any
    unit: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ExtractionRecord(BaseModel):
    """Structured record produced by downstream extractors."""

    source_component: DocumentComponent
    fields: List[ExtractedField] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class LiteratureExtractionResult(BaseModel):
    """Top-level container for the pipeline output."""

    source_id: str
    components: List[DocumentComponent]
    records: List[ExtractionRecord]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionSuggestion(BaseModel):
    """Represents a candidate MCP tool invocation derived from literature."""

    tool_name: str
    args: Dict[str, Any]
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: List[Dict[str, Any]] = Field(default_factory=list)
