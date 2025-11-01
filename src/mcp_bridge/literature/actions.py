"""Mapping of extracted literature data to MCP action suggestions."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Dict, List, Optional, Tuple

from .models import ActionSuggestion, ExtractedField, ExtractionRecord, LiteratureExtractionResult

DEFAULT_FIELD_PARAMETER_MAP: Dict[str, Tuple[str, str]] = {
    "body_weight_kg": ("Organism|Weight", "kg"),
    "dose_mg": ("Protocol|Dose", "mg"),
}

TABLE_KEYWORDS: Dict[str, Tuple[str, str]] = {
    "weight": ("Organism|Weight", "kg"),
    "dose": ("Protocol|Dose", "mg"),
}


class LiteratureActionMapper:
    """Convert extraction results into actionable MCP tool suggestions."""

    def __init__(
        self,
        *,
        simulation_id: str,
        field_parameter_map: Dict[str, Tuple[str, str]] | None = None,
    ) -> None:
        self._simulation_id = simulation_id
        self._field_parameter_map = field_parameter_map or DEFAULT_FIELD_PARAMETER_MAP

    def map_actions(self, extraction: LiteratureExtractionResult) -> List[ActionSuggestion]:
        accumulator: Dict[str, Dict[str, object]] = defaultdict(
            lambda: {
                "unit": None,
                "values": [],
                "confidences": [],
                "provenance": [],
            }
        )

        for record in extraction.records:
            for field in record.fields:
                self._ingest_field(accumulator, record, field)

        suggestions: List[ActionSuggestion] = []
        for parameter_path, data in accumulator.items():
            values: List[float] = data["values"]  # type: ignore[assignment]
            if not values:
                continue
            unit = data["unit"]
            confidences: List[float] = data["confidences"]  # type: ignore[assignment]
            provenance = data["provenance"]  # type: ignore[assignment]
            value = mean(values)
            confidence = mean(confidences) if confidences else 0.5
            summary = (
                f"Set {parameter_path} to {value:.3g} {unit} derived from {len(values)} "
                "literature value(s)."
            )
            suggestions.append(
                ActionSuggestion(
                    tool_name="set_parameter_value",
                    args={
                        "simulationId": self._simulation_id,
                        "parameterPath": parameter_path,
                        "value": value,
                        "unit": unit,
                        "comment": "Extracted from literature sources",
                    },
                    summary=summary,
                    confidence=confidence,
                    provenance=provenance,
                )
            )

        return suggestions

    def _ingest_field(
        self,
        accumulator: Dict[str, Dict[str, object]],
        record: ExtractionRecord,
        field: ExtractedField,
    ) -> None:
        component = record.source_component
        mapping = self._field_parameter_map.get(field.name)
        if mapping:
            parameter_path, unit = mapping
            value = self._coerce_float(field.value)
            if value is not None:
                self._append_entry(
                    accumulator,
                    parameter_path,
                    unit,
                    value,
                    field.confidence,
                    component.component_id,
                    component.page,
                )
            return

        if field.name == "table_rows" and isinstance(field.value, list):
            for row in field.value:
                if not isinstance(row, dict):
                    continue
                for key, raw_value in row.items():
                    parameter_info = self._match_table_column(key)
                    if not parameter_info:
                        continue
                    parameter_path, unit = parameter_info
                    value = self._coerce_float(raw_value)
                    if value is None:
                        continue
                    self._append_entry(
                        accumulator,
                        parameter_path,
                        unit,
                        value,
                        field.confidence,
                        component.component_id,
                        component.page,
                    )

    @staticmethod
    def _match_table_column(column_name: str) -> Optional[Tuple[str, str]]:
        lower = column_name.lower()
        for keyword, mapping in TABLE_KEYWORDS.items():
            if keyword in lower:
                return mapping
        return None

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                cleaned = value.replace(",", "").strip()
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _append_entry(
        accumulator: Dict[str, Dict[str, object]],
        parameter_path: str,
        unit: str,
        value: float,
        confidence: float,
        component_id: str,
        page: int,
    ) -> None:
        bucket = accumulator[parameter_path]
        if bucket["unit"] is None:
            bucket["unit"] = unit
        bucket["values"].append(value)  # type: ignore[call-arg]
        bucket["confidences"].append(confidence)  # type: ignore[call-arg]
        bucket["provenance"].append(  # type: ignore[call-arg]
            {"componentId": component_id, "page": page}
        )
