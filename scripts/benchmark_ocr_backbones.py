"""Benchmark OCR backbones (PaddleOCR vs Tesseract+DocTR) on the gold set."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Literal


def _load_goldset_entries(root: Path) -> list[dict[str, str]]:
    manifest = root / "index.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return [entry for entry in entries if "pdf" in entry]


def _benchmark_stub(entries: Iterable[dict[str, str]], backend: str) -> list[dict[str, object]]:
    # Placeholder for real benchmarking logic.
    results = []
    start = time.perf_counter()
    for entry in entries:
        results.append({"sourceId": entry["sourceId"], "backend": backend, "latency_ms": 0})
    duration = (time.perf_counter() - start) * 1000
    return results, duration


@dataclass
class BenchmarkResult:
    backend: Literal["paddleocr", "tesseract_doctr"]
    mean_latency_ms: float
    total_documents: int
    notes: str


def run_benchmark(goldset_root: Path, backend: str) -> BenchmarkResult:
    entries = _load_goldset_entries(goldset_root)
    results, duration_ms = _benchmark_stub(entries, backend)
    mean_latency = duration_ms / max(len(entries), 1)
    return BenchmarkResult(
        backend=backend,
        mean_latency_ms=mean_latency,
        total_documents=len(entries),
        notes="stub results – replace with real OCR pipeline",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", type=Path, default=Path("reference/goldset"))
    parser.add_argument("--output", type=Path, default=Path("docs/research/ocr_benchmark.json"))
    args = parser.parse_args()

    backends = ["paddleocr", "tesseract_doctr"]
    results = [run_benchmark(args.goldset, backend) for backend in backends]
    payload = {"results": [asdict(result) for result in results], "generatedAt": time.time()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved benchmark results to {args.output}")


if __name__ == "__main__":
    main()
