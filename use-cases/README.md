# MCP Bridge Use-Case Packs

This directory bundles reproducible notebooks that demonstrate the value
delivered by the MCP bridge. Each scenario ships with the inputs, code snippets,
and reference metrics needed to reproduce the results on the in-memory adapter
(or against a real OSPSuite backend once available).

| Notebook | Scenario | Highlights |
| --- | --- | --- |
| `sensitivity-in-minutes.ipynb` | Rapid sensitivity sweep on the Midazolam model. | <10 minute wall-clock, PK metric deltas ≤ ±1%. |
| `population-scale.ipynb` | Population run at scale (1k × 10 replicates). | Validates throughput targets and artefact storage. |
| `literature-assisted-calibration.ipynb` | Uses literature extraction to seed parameter updates. | fact_accuracy ≥ 0.95, table_row_recall ≥ 0.9 before applying calibration suggestions. |

## How to run

1. Create a virtual environment and install the bridge: `pip install -e '.[dev]'`.
2. Launch JupyterLab/Notebook: `jupyter lab` (or `jupyter notebook`).
3. Open one of the notebooks and execute the cells from top to bottom.

Each notebook spins up an in-memory FastAPI app via `TestClient`, so no external
services are required. When using the `subprocess` adapter, ensure R/OSPSuite
libraries are installed and set `ADAPTER_BACKEND=subprocess` in the relevant
cells.

## Metrics & artefacts

Reference metrics are embedded in the notebooks and align with the thresholds
documented in `docs/mcp-bridge/performance-plan.md` and the literature quality
gates. If your environment deviates, document the delta and attach artefacts to
the change-management checklist.
