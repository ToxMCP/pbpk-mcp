"""Tests for mapping literature extraction outputs to MCP actions."""

from __future__ import annotations

from pathlib import Path

from mcp_bridge.literature.actions import LiteratureActionMapper
from mcp_bridge.literature.extractors import (
    HeuristicTextExtractor,
    PdfExtractKitClient,
    PdfExtractKitLayoutExtractor,
    SimpleFigureExtractor,
    SimpleTableExtractor,
)
from mcp_bridge.literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies


def _run_pipeline(tmp_path) -> LiteratureActionMapper:
    fixture_json = Path("tests/fixtures/literature/pdf_extract_kit_sample.pdf.json")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    pdf_path.with_suffix(".pdf.json").write_text(fixture_json.read_text())

    client = PdfExtractKitClient(output_suffix=".json")
    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=PdfExtractKitLayoutExtractor(client),
            text_extractor=HeuristicTextExtractor(),
            table_extractor=SimpleTableExtractor(),
            figure_extractor=SimpleFigureExtractor(),
        )
    )
    extraction = pipeline.run(str(pdf_path), source_id="paper-renal")
    mapper = LiteratureActionMapper(simulation_id="renal-study")
    actions = mapper.map_actions(extraction)
    return actions


def test_action_mapper_produces_weight_and_dose_actions(tmp_path) -> None:
    actions = _run_pipeline(tmp_path)
    assert actions, "Expected at least one action suggestion"

    by_path = {action.args["parameterPath"]: action for action in actions}
    weight_action = by_path.get("Organism|Weight")
    dose_action = by_path.get("Protocol|Dose")

    assert weight_action is not None
    assert weight_action.tool_name == "set_parameter_value"
    assert abs(weight_action.args["value"] - 71.0) < 1e-6
    assert weight_action.args["unit"] == "kg"
    assert weight_action.args["simulationId"] == "renal-study"
    assert "Organism|Weight" in weight_action.summary
    assert 0.0 <= weight_action.confidence <= 1.0
    assert weight_action.provenance

    assert dose_action is not None
    assert abs(dose_action.args["value"] - 40.0) < 1e-6
    assert dose_action.args["unit"] == "mg"
