"""Orchestration for literature PDF ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .interfaces import (
    FigureExtractor,
    LayoutExtractor,
    PostProcessor,
    TableExtractor,
    TextExtractor,
)
from .models import ComponentType, ExtractionRecord, LiteratureExtractionResult
from .validation import ExtractionSchemaValidator, default_validator


@dataclass
class PipelineDependencies:
    """Container for pluggable extractor implementations."""

    layout_extractor: LayoutExtractor
    text_extractor: TextExtractor
    table_extractor: TableExtractor
    figure_extractor: FigureExtractor
    post_processors: Optional[Iterable[PostProcessor]] = None


class LiteratureIngestionPipeline:
    """Run the literature extraction flow for a PDF document."""

    def __init__(
        self,
        deps: PipelineDependencies,
        *,
        validator: ExtractionSchemaValidator | None = None,
    ) -> None:
        self._deps = deps
        self._validator = validator or default_validator

    def run(self, pdf_path: str, *, source_id: Optional[str] = None) -> LiteratureExtractionResult:
        components = list(self._deps.layout_extractor.extract(pdf_path))
        records: List[ExtractionRecord] = []

        for component in components:
            if component.type is ComponentType.TEXT:
                records.append(self._deps.text_extractor.extract(component))
            elif component.type is ComponentType.TABLE:
                records.append(self._deps.table_extractor.extract(component))
            elif component.type is ComponentType.FIGURE:
                records.append(self._deps.figure_extractor.extract(component))
            else:  # pragma: no cover - future components
                continue

        result = LiteratureExtractionResult(
            source_id=source_id or pdf_path,
            components=components,
            records=records,
        )

        for processor in self._deps.post_processors or ():
            result = processor.refine(result)

        self._inject_provenance_defaults(result)
        self._validator.validate_result(result)

        return result

    @staticmethod
    def _inject_provenance_defaults(result: LiteratureExtractionResult) -> None:
        for record in result.records:
            component = record.source_component
            for field in record.fields:
                provenance = field.provenance
                if not isinstance(provenance, dict):
                    provenance = {}
                    field.provenance = provenance
                provenance.setdefault("sourceId", result.source_id)
                provenance.setdefault("componentId", component.component_id)
                provenance.setdefault("page", component.page)
