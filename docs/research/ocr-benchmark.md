# OCR Backbone Benchmark

**Date:** 2025-10-30  
**Author:** Platform Research  
**Backbones:** PaddleOCR vs. Tesseract + DocTR  
**Gold set:** `reference/goldset/` (30 PDFs with tables and figures)

---

## 1. Objectives

1. Quantify latency and accuracy trade-offs between PaddleOCR and the
   Tesseract+DocTR combination.
2. Determine the default OCR backbone for the literature ingestion pipeline.
3. Provide actionable guidance for runtime selection (CPU vs. GPU availability).

## 2. Methodology

- Used `scripts/benchmark_ocr_backbones.py` to iterate over the gold-set
  manifest and measure per-document latency. The script currently contains a
  placeholder stub—real integration should wrap the existing OCR interface in
  `mcp_bridge.literature.extractors`.
- Accuracy metrics leverage the literature evaluation harness, reusing
  `make goldset-eval` thresholds (`fact_accuracy ≥ 0.95`, `table_row_recall ≥ 0.9`).
- Benchmarks were executed on a CPU-only machine (8 vCPU, 16 GB RAM). GPU
  support remains future work.

## 3. Results (preliminary)

| Backbone | Mean latency (ms) | Total docs | Accuracy status | Notes |
| --- | --- | --- | --- | --- |
| PaddleOCR | 0.00008 | 30 | TBD (requires pipeline integration) | Baseline stub values. |
| Tesseract + DocTR | 0.00007 | 30 | TBD | Baseline stub values. |

*Latency numbers are placeholders until pipeline integration is finalized.*

## 4. Decision

**Pending**: integrate real OCR runners and populate accuracy metrics. The
current stub does not reflect actual performance. Steps to complete:

1. Swap `_benchmark_stub` with calls to the actual OCR modules.
2. Persist extracted text/table outputs and feed them through the evaluation
   harness to compute accuracy scores.
3. Update this document with final numbers and recommendation.

## 5. Follow-up Actions

- [ ] Implement real OCR benchmarking in `scripts/benchmark_ocr_backbones.py`.
- [ ] Record accuracy metrics using `scripts/evaluate_goldset.py` outputs.
- [ ] Decide default backbone (document rationale) and update
      `docs/mcp-bridge/pdf-literature-pipeline.md`.

## 6. Artefacts

- Raw timing stub: `docs/research/ocr_benchmark.json`
- Script: `scripts/benchmark_ocr_backbones.py`

---

## Appendix A – Environment

- Python 3.9
- CPU: 8 vCPU (Intel)
- Memory: 16 GB
- Dependencies: see `pyproject.toml`
