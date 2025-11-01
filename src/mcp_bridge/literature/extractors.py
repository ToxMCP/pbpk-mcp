"""Extractor implementations backed by PDF-Extract-Kit style outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

from .interfaces import FigureExtractor, LayoutExtractor, TableExtractor, TextExtractor
from .models import (
    BoundingBox,
    ComponentType,
    DocumentComponent,
    ExtractedField,
    ExtractionRecord,
)

_TYPE_MAP: Mapping[str, ComponentType] = {
    "text": ComponentType.TEXT,
    "table": ComponentType.TABLE,
    "figure": ComponentType.FIGURE,
}


class PdfExtractKitClient:
    """Simple client that reads pre-generated JSON emitted by PDF-Extract-Kit."""

    def __init__(self, output_suffix: str = ".json") -> None:
        self._suffix = output_suffix

    def run(self, pdf_path: str) -> Mapping[str, object]:
        json_path = Path(pdf_path + self._suffix)
        if not json_path.is_file():
            raise FileNotFoundError(f"Expected PDF-Extract-Kit JSON output at {json_path}")
        return json.loads(json_path.read_text())


class PdfExtractKitLayoutExtractor(LayoutExtractor):
    """Create `DocumentComponent` instances from PDF-Extract-Kit JSON output."""

    def __init__(self, client: PdfExtractKitClient | None = None) -> None:
        self._client = client or PdfExtractKitClient()

    def extract(self, pdf_path: str) -> Iterable[DocumentComponent]:  # type: ignore[override]
        payload = self._client.run(pdf_path)
        pages = payload.get("pages", []) if isinstance(payload, Mapping) else []
        components: List[DocumentComponent] = []
        for page_entry in pages:
            if not isinstance(page_entry, Mapping):
                continue
            page_number = int(page_entry.get("page", 1))
            for block in page_entry.get("blocks", []):
                if not isinstance(block, Mapping):
                    continue
                raw_type = str(block.get("type", "text")).lower()
                component_type = _TYPE_MAP.get(raw_type)
                if not component_type:
                    continue
                bbox = block.get("bbox") or block.get("bounding_box")
                if not isinstance(bbox, Sequence) or len(bbox) != 4:
                    continue
                component = DocumentComponent(
                    component_id=str(block.get("id") or f"page{page_number}-{len(components)}"),
                    page=page_number,
                    type=component_type,
                    bbox=BoundingBox(x0=float(bbox[0]), y0=float(bbox[1]), x1=float(bbox[2]), y1=float(bbox[3])),
                    text=block.get("text") if isinstance(block.get("text"), str) else None,
                    metadata={k: v for k, v in block.items() if k not in {"bbox", "bounding_box"}},
                )
                components.append(component)
        return components


class HeuristicTextExtractor(TextExtractor):
    """Extract simple numeric facts from free-form text using regex heuristics."""

    def __init__(self) -> None:
        self._patterns: Sequence[tuple[re.Pattern[str], str, callable]] = (
            (re.compile(r"weight\s+(?:is|=)\s*(\d+(?:\.\d+)?)\s*kg", re.I), "body_weight_kg", float),
            (re.compile(r"dose\s+(?:is|=)\s*(\d+(?:\.\d+)?)\s*mg", re.I), "dose_mg", float),
        )

    def extract(self, component: DocumentComponent) -> ExtractionRecord:  # type: ignore[override]
        fields: List[ExtractedField] = []
        text = component.text or component.metadata.get("text") or ""
        if isinstance(text, str):
            for pattern, name, caster in self._patterns:
                match = pattern.search(text)
                if match:
                    try:
                        value = caster(match.group(1))
                    except ValueError:
                        continue
                    fields.append(
                        ExtractedField(
                            name=name,
                            value=value,
                            unit="kg" if name.endswith("kg") else "mg",
                            confidence=0.8,
                            provenance={"pattern": pattern.pattern, "sourceText": text},
                        )
                    )
            fields.append(
                ExtractedField(
                    name="raw_text",
                    value=text.strip(),
                    confidence=0.6,
                )
            )
        return ExtractionRecord(source_component=component, fields=fields)


class SimpleTableExtractor(TableExtractor):
    """Normalise table cells into structured field records."""

    def extract(self, component: DocumentComponent) -> ExtractionRecord:  # type: ignore[override]
        table = component.metadata.get("table")
        fields: List[ExtractedField] = []
        if isinstance(table, Mapping):
            headers = table.get("headers")
            rows = table.get("rows")
            if isinstance(headers, list) and isinstance(rows, list):
                normalized = [dict(zip(headers, row)) for row in rows if isinstance(row, list)]
                fields.append(
                    ExtractedField(
                        name="table_rows",
                        value=normalized,
                        confidence=0.9,
                    )
                )
        return ExtractionRecord(source_component=component, fields=fields)


@dataclass
class FigureAsset:
    """Metadata describing an extracted figure asset."""

    image_path: str
    caption: str | None = None


class SimpleFigureExtractor(FigureExtractor):
    """Capture figure references for downstream plot digitisation."""

    def extract(self, component: DocumentComponent) -> ExtractionRecord:  # type: ignore[override]
        metadata = component.metadata
        image_path = metadata.get("image_path")
        caption = metadata.get("caption")
        fields: List[ExtractedField] = []
        if isinstance(image_path, str):
            fields.append(
                ExtractedField(
                    name="figure_asset",
                    value=asdict(FigureAsset(image_path=image_path, caption=caption)),
                    confidence=0.7,
                )
            )
        return ExtractionRecord(source_component=component, fields=fields)
