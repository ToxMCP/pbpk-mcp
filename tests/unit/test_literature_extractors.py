"""Tests for PDF-Extract-Kit backed extractor implementations."""

from __future__ import annotations

from pathlib import Path

from mcp_bridge.literature.extractors import (
    HeuristicTextExtractor,
    PdfExtractKitClient,
    PdfExtractKitLayoutExtractor,
    SimpleFigureExtractor,
    SimpleTableExtractor,
)
from mcp_bridge.literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies


FIXTURE_PDF = str(Path("tests/fixtures/literature/pdf_extract_kit_sample.pdf"))


def _create_pipeline() -> LiteratureIngestionPipeline:
    client = PdfExtractKitClient(output_suffix=".json")
    layout = PdfExtractKitLayoutExtractor(client)
    text = HeuristicTextExtractor()
    table = SimpleTableExtractor()
    figure = SimpleFigureExtractor()
    return LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=layout,
            text_extractor=text,
            table_extractor=table,
            figure_extractor=figure,
        )
    )


def test_pdf_extract_kit_layout_extractor_parses_blocks(tmp_path) -> None:
    fixture_json = Path("tests/fixtures/literature/pdf_extract_kit_sample.pdf.json")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    fixture_copy = pdf_path.with_suffix(".pdf.json")
    fixture_copy.write_text(fixture_json.read_text())

    pipeline = _create_pipeline()
    result = pipeline.run(str(pdf_path))

    assert len(result.components) == 3
    assert any(field.name == "body_weight_kg" for record in result.records for field in record.fields)
    table_fields = [field for record in result.records for field in record.fields if field.name == "table_rows"]
    assert table_fields and table_fields[0].value[0]["Subject"] == "A"
    figure_fields = [field for record in result.records for field in record.fields if field.name == "figure_asset"]
    assert figure_fields and figure_fields[0].value["image_path"].endswith("page1_fig1.png")

