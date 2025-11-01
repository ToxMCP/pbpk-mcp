"""Evaluation utilities for literature extraction accuracy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from .models import ExtractedField, ExtractionRecord, LiteratureExtractionResult


@dataclass
class GoldFact:
    name: str
    value: float
    unit: Optional[str] = None
    tolerance: float = 0.0


@dataclass
class GoldTable:
    component_id: str
    rows: List[Mapping[str, str]]


@dataclass
class EvaluationFixture:
    source_id: str
    facts: List[GoldFact]
    tables: List[GoldTable]


@dataclass
class FactScore:
    name: str
    expected: float
    observed: Optional[float]
    unit: Optional[str]
    within_tolerance: bool


@dataclass
class TableScore:
    component_id: str
    expected_rows: int
    matched_rows: int


@dataclass
class EvaluationReport:
    source_id: str
    fact_scores: List[FactScore]
    table_scores: List[TableScore]

    @property
    def fact_accuracy(self) -> float:
        if not self.fact_scores:
            return 0.0
        successes = sum(1 for score in self.fact_scores if score.within_tolerance)
        return successes / len(self.fact_scores)

    @property
    def table_row_recall(self) -> float:
        total_expected = sum(score.expected_rows for score in self.table_scores)
        if total_expected == 0:
            return 0.0
        total_matched = sum(score.matched_rows for score in self.table_scores)
        return total_matched / total_expected


def load_fixture(path: str | Path) -> EvaluationFixture:
    payload = json.loads(Path(path).read_text())
    facts = [
        GoldFact(
            name=item["name"],
            value=float(item["value"]),
            unit=item.get("unit"),
            tolerance=float(item.get("tolerance", 0.0)),
        )
        for item in payload.get("facts", [])
    ]
    tables = [
        GoldTable(component_id=table["componentId"], rows=list(table.get("rows", [])))
        for table in payload.get("tables", [])
    ]
    return EvaluationFixture(
        source_id=payload.get("sourceId", "unknown"), facts=facts, tables=tables
    )


def evaluate(
    extraction: LiteratureExtractionResult, fixture: EvaluationFixture
) -> EvaluationReport:
    fact_scores = _score_facts(extraction.records, fixture.facts)
    table_scores = _score_tables(extraction.records, fixture.tables)
    return EvaluationReport(
        source_id=fixture.source_id, fact_scores=fact_scores, table_scores=table_scores
    )


def _score_facts(records: Iterable[ExtractionRecord], facts: Iterable[GoldFact]) -> List[FactScore]:
    field_index: Dict[str, ExtractedField] = {}
    for record in records:
        for field in record.fields:
            if isinstance(field.value, (int, float)):
                field_index.setdefault(field.name, field)

    scores: List[FactScore] = []
    for fact in facts:
        field = field_index.get(fact.name)
        observed_value = float(field.value) if field else None
        within = False
        if observed_value is not None:
            within = abs(observed_value - fact.value) <= fact.tolerance
        scores.append(
            FactScore(
                name=fact.name,
                expected=fact.value,
                observed=observed_value,
                unit=fact.unit,
                within_tolerance=within,
            )
        )
    return scores


def _score_tables(
    records: Iterable[ExtractionRecord], tables: Iterable[GoldTable]
) -> List[TableScore]:
    table_index: Dict[str, ExtractionRecord] = {
        record.source_component.component_id: record for record in records
    }
    scores: List[TableScore] = []
    for table in tables:
        record = table_index.get(table.component_id)
        matched = 0
        if record:
            for field in record.fields:
                if field.name == "table_rows" and isinstance(field.value, list):
                    matched = len(field.value)
        scores.append(
            TableScore(
                component_id=table.component_id,
                expected_rows=len(table.rows),
                matched_rows=matched,
            )
        )
    return scores
