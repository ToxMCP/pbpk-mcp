"""Tests for literature extraction evaluation harness."""

from __future__ import annotations

from pathlib import Path

from mcp_bridge.literature.actions import LiteratureActionMapper
from mcp_bridge.literature.evaluation import evaluate, load_fixture
from mcp_bridge.literature.extractors import (
    HeuristicTextExtractor,
    PdfExtractKitClient,
    PdfExtractKitLayoutExtractor,
    SimpleFigureExtractor,
    SimpleTableExtractor,
)
from mcp_bridge.literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies


def _run_pipeline(tmp_path):
    fixture_json = Path("tests/fixtures/literature/pdf_extract_kit_sample.pdf.json")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    (pdf_path.parent / f"{pdf_path.name}.json").write_text(fixture_json.read_text())

    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=PdfExtractKitLayoutExtractor(PdfExtractKitClient()),
            text_extractor=HeuristicTextExtractor(),
            table_extractor=SimpleTableExtractor(),
            figure_extractor=SimpleFigureExtractor(),
        )
    )
    extraction = pipeline.run(str(pdf_path), source_id="paper-renal")
    mapper = LiteratureActionMapper(simulation_id="renal-study")
    actions = mapper.map_actions(extraction)
    return extraction, actions


def test_evaluation_report_scores_accuracy(tmp_path) -> None:
    extraction, actions = _run_pipeline(tmp_path)
    fixture = load_fixture("tests/fixtures/literature/gold_standard.json")
    report = evaluate(extraction, fixture)

    assert report.fact_scores
    assert report.fact_accuracy == 1.0
    assert report.table_row_recall == 1.0

    # ensure mapped actions align with evaluation facts
    paths = {action.args["parameterPath"] for action in actions}
    assert "Organism|Weight" in paths
    assert "Protocol|Dose" in paths
