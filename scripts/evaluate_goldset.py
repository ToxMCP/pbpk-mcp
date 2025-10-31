#!/usr/bin/env python3
"""Evaluate the literature extraction pipeline against the curated gold set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Iterable

from mcp_bridge.literature.evaluation import evaluate, load_fixture
from mcp_bridge.literature.extractors import (
    HeuristicTextExtractor,
    PdfExtractKitLayoutExtractor,
    SimpleFigureExtractor,
    SimpleTableExtractor,
)
from mcp_bridge.literature.pipeline import LiteratureIngestionPipeline, PipelineDependencies


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "entries" not in payload or not isinstance(payload["entries"], list):
        raise ValueError(f"Manifest {path} is missing an 'entries' array")
    return payload


def _iter_entries(manifest: dict, root: Path) -> Iterable[tuple[str, Path, Path]]:
    for entry in manifest["entries"]:
        source_id = entry["sourceId"]
        pdf_path = root / entry["pdf"]
        annotation_path = root / entry["annotation"]
        yield source_id, pdf_path, annotation_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate extraction quality on the gold set.")
    parser.add_argument(
        "--manifest",
        default=Path("reference/goldset/index.json"),
        type=Path,
        help="Path to gold-set manifest (default: reference/goldset/index.json)",
    )
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit with non-zero status if aggregate metrics fall below thresholds.",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    manifest = _load_manifest(manifest_path)
    root = manifest_path.parent

    pipeline = LiteratureIngestionPipeline(
        PipelineDependencies(
            layout_extractor=PdfExtractKitLayoutExtractor(),
            text_extractor=HeuristicTextExtractor(),
            table_extractor=SimpleTableExtractor(),
            figure_extractor=SimpleFigureExtractor(),
        )
    )

    reports = []
    print(f"Evaluating gold set located at {root}")
    for source_id, pdf_path, annotation_path in _iter_entries(manifest, root):
        if not pdf_path.is_file():
            raise SystemExit(f"PDF missing for {source_id}: {pdf_path}")
        if not annotation_path.is_file():
            raise SystemExit(f"Annotation missing for {source_id}: {annotation_path}")

        extraction = pipeline.run(str(pdf_path), source_id=source_id)
        fixture = load_fixture(annotation_path)
        report = evaluate(extraction, fixture)
        reports.append(report)
        print(
            f" - {source_id}: fact_accuracy={report.fact_accuracy:.3f}, "
            f"table_row_recall={report.table_row_recall:.3f}"
        )

    if not reports:
        raise SystemExit("No entries discovered in manifest.")

    avg_fact = mean(report.fact_accuracy for report in reports)
    avg_table = mean(report.table_row_recall for report in reports)
    print(
        f"\nAggregate metrics across {len(reports)} documents:\n"
        f"  Fact accuracy     : {avg_fact:.3f}\n"
        f"  Table row recall  : {avg_table:.3f}"
    )

    thresholds = manifest.get("thresholds", {})
    fact_threshold = float(thresholds.get("fact_accuracy", 0.0))
    table_threshold = float(thresholds.get("table_row_recall", 0.0))

    if args.fail_on_threshold:
        failed = []
        if avg_fact < fact_threshold:
            failed.append(f"fact_accuracy ({avg_fact:.3f} < {fact_threshold:.3f})")
        if avg_table < table_threshold:
            failed.append(f"table_row_recall ({avg_table:.3f} < {table_threshold:.3f})")
        if failed:
            raise SystemExit("Threshold check failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
