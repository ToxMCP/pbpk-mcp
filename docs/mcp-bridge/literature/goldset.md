# Literature Gold Set

To validate the literature ingestion pipeline we curate a synthetic, deterministic corpora
containing **30** study reports. Each document ships with:

- `papers/paper-XXX.pdf` – a lightweight single-page PDF with the study summary
- `papers/paper-XXX.pdf.json` – PdfExtractKit-style layout payload consumed by the pipeline
- `annotations/paper-XXX.json` – ground-truth facts and table rows
- `thumbnails/paper-XXX.png` – QA thumbnail placeholder

All artefacts live under `reference/goldset/`. The dataset is intentionally generated from
code so that new contributors can reproduce the exact contents without downloading large
external archives.

## Regenerating the dataset

```
python scripts/build_goldset.py
```

The script will overwrite the existing PDFs, layout payloads, annotations, thumbnails, and
manifest file (`index.json`). Each entry embeds two scalar facts (`body_weight_kg`,
`dose_mg`) and a three-row cohort table.

## Evaluating the pipeline

```
make goldset-eval
```

This command runs the pipeline over every document using the PdfExtractKit layout extractor
and household heuristics. It then evaluates the outputs against the annotations, enforcing
the scorecard targets (`fact_accuracy ≥ 0.95`, `table_row_recall ≥ 0.90`). The command fails
if the aggregate metrics fall below the thresholds.

For ad-hoc runs:

```
python scripts/evaluate_goldset.py --manifest reference/goldset/index.json
```

## Updating thresholds or annotations

1. Modify the dataset definition list in `scripts/build_goldset.py`.
2. Regenerate the artefacts and re-run `make goldset-eval`.
3. Commit the updated PDFs, annotations, thumbnails, and manifest.
4. Include a short note in the release changelog describing the new metrics.

Because the gold set intentionally mirrors the heuristic extractors, it serves as a fast
sanity check in CI while longer-running extraction benchmarks can focus on real-world PDFs.
