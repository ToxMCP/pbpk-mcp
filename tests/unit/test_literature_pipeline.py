"""Unit tests for the literature ingestion pipeline."""

from __future__ import annotations

from typing import Iterable

import pytest

from mcp_bridge.literature.interfaces import FigureExtractor, LayoutExtractor, TableExtractor, TextExtractor
from mcp_bridge.literature.models import (
    BoundingBox,
    ComponentType,
    DocumentComponent,
    ExtractedField,
    ExtractionRecord,
)
from mcp_bridge.literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies
from mcp_bridge.literature.validation import ExtractionSchemaError


class DummyLayout(LayoutExtractor):
    def __init__(self, components: Iterable[DocumentComponent]) -> None:
        self._components = list(components)

    def extract(self, pdf_path: str):  # type: ignore[override]
        return list(self._components)


class DummyExtractor(TextExtractor, TableExtractor, FigureExtractor):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def extract(self, component: DocumentComponent) -> ExtractionRecord:  # type: ignore[override]
        field = ExtractedField(name="source", value=self.tag, confidence=1.0)
        return ExtractionRecord(source_component=component, fields=[field])


def _component(component_id: str, type_: ComponentType, page: int = 1) -> DocumentComponent:
    return DocumentComponent(
        component_id=component_id,
        page=page,
        type=type_,
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=100),
    )


def test_pipeline_routes_components_to_correct_extractors() -> None:
    components = [
        _component("c1", ComponentType.TEXT),
        _component("c2", ComponentType.TABLE),
        _component("c3", ComponentType.FIGURE),
    ]
    layout = DummyLayout(components)
    text = DummyExtractor("text")
    table = DummyExtractor("table")
    figure = DummyExtractor("figure")

    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=layout,
            text_extractor=text,
            table_extractor=table,
            figure_extractor=figure,
        )
    )

    result = pipeline.run("dummy.pdf", source_id="paper-1")

    assert result.source_id == "paper-1"
    assert len(result.records) == 3
    assert [record.fields[0].value for record in result.records] == ["text", "table", "figure"]
    for record in result.records:
        field = record.fields[0]
        assert field.provenance["sourceId"] == "paper-1"
        assert field.provenance["componentId"] == record.source_component.component_id
        assert field.provenance["page"] == record.source_component.page


def test_pipeline_applies_post_processors() -> None:
    components = [_component("c1", ComponentType.TEXT)]
    layout = DummyLayout(components)
    text = DummyExtractor("text")

    class AppendMetadata:
        def __init__(self) -> None:
            self.called = False

        def refine(self, result):
            self.called = True
            result.metadata["post"] = True
            return result

    post = AppendMetadata()
    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=layout,
            text_extractor=text,
            table_extractor=DummyExtractor("table"),
            figure_extractor=DummyExtractor("figure"),
            post_processors=[post],
        )
    )

    result = pipeline.run("dummy.pdf")
    assert post.called
    assert result.metadata["post"] is True


def test_pipeline_raises_on_schema_violation() -> None:
    components = [_component("", ComponentType.TEXT)]
    layout = DummyLayout(components)
    text = DummyExtractor("text")

    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=layout,
            text_extractor=text,
            table_extractor=DummyExtractor("table"),
            figure_extractor=DummyExtractor("figure"),
        )
    )

    with pytest.raises(ExtractionSchemaError):
        pipeline.run("invalid.pdf", source_id="paper-2")
