# Literature-to-Model PDF Pipeline Blueprint

## Goals

- Extract dosing regimens, subject demographics, compound properties, and digitised PK curves from scientific PDFs with high fidelity.
- Preserve document layout so values keep their contextual headers/units.
- Produce structured output that downstream agents can map to MCP tool calls with human confirmation.
- Provide an evaluation baseline and roadmap for hardened, regulated environments.

## Functional & Non-Functional Requirements

- **Layout awareness**: multi-column articles, tables, call-outs, and figure captions must remain linked to numeric values.
- **Tables & figures**: support for compound property tables, dosing schedules, and PK plots (digitisation).
- **Metadata enrichment**: capture provenance (page, bounding boxes, confidence) for audit.
- **Human-in-the-loop ready**: extracted fields need confidence scores and source snippets to surface during confirmation.
- **Extensibility**: interchange components (OCR, LLM) without rewriting the pipeline; support GPU acceleration but operate in CPU-only fallback mode for lightweight tasks.
- **Security/compliance**: keep processing on-prem or in VPC where required; redact PHI if detected.

## Candidate Tooling Comparison

| Capability | PDF-Extract-Kit (open-source) | GROBID | Azure Document Intelligence (Form Recognizer) |
|------------|-------------------------------|--------|-----------------------------------------------|
| **License / Cost** | Apache 2.0, free | Apache 2.0 | Commercial (pay-per-page) |
| **Layout detection** | YOLOX + LayoutLMv3 for fine-grained blocks (GPU recommended) | Focused on scholarly metadata; limited layout classification | Built-in page/line/block segmentation with high accuracy |
| **Table extraction** | Table structure recognition via PaddleOCR/TableMaster; exports JSON/CSV | Basic TEI table tags; struggles with complex spanning cells | Structured table output with confidence + key-value pairs |
| **Figure handling** | Produces cropped images + bounding boxes, ready for downstream plot digitisation | Minimal support (citations/headers only) | Returns figure regions but no data digitisation |
| **Text extraction** | Hybrid OCR + text layer recovery; retains coordinates | Good for plain text, loses detailed geometry | High quality OCR, layout metadata, language detection |
| **LLM integration** | Neutral—DIY orchestration required; pairs well with multimodal LLMs | None (classical NLP stack) | Native integration with Azure OpenAI for field extraction |
| **Deployment** | Self-hosted Docker; GPU optional but improves throughput | Java service + external models; CPU-friendly | Managed SaaS; region availability & data residency constraints |
| **Community / Maturity** | Active (2024–2025) GitHub releases, multilingual | Mature academic project but limited updates | Enterprise support, SLAs |

**Recommendation**: adopt a hybrid stack—self-host PDF-Extract-Kit for layout + table segmentation, then layer specialised components (e.g., paddleocr/table-transformer, PlotDigitizer/PlotExtract, GPT-4o/Claude 3.5 Sonnet) for semantic extraction. Keep Azure/other SaaS as optional accelerator when compliance allows, but design for on-prem portability.

## Reference Pipeline Architecture

```
┌────────────┐   ┌──────────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
│ PDF Intake │─▶│ Layout Detection │─▶│ Component Routing      │─▶│ Extraction Workers     │
└────────────┘   │ (PDF-Extract-Kit) │   │ (text / tables / figs) │   │  • Text: OCR + chunk   │
                 └────────┬─────────┘   └──────────┬────────────┘   │  • Tables: TableMaster │
                          │                      │                  │  • Plots: PlotExtract  │
                          ▼                      ▼                  └─────────┬─────────────┘
                 ┌────────────────┐   ┌────────────────────┐                   │
                 │ Normalisation  │   │ Fact Extraction     │◀─ LLM (GPT-4o,    │
                 │  (units, types)│   │  (entity/value map) │   Claude 3, etc.  │
                 └──────┬─────────┘   └─────────┬──────────┘                   │
                        ▼                       ▼                              ▼
                 ┌──────────────┐       ┌──────────────────┐         ┌────────────────────┐
                 │ Canonical DB │◀────▶│ Vector Store (RAG)│         │ QA & Scoring       │
                 │ (Postgres)   │       │ (e.g., PgVector)  │         │ - confidence       │
                 └──────┬───────┘       └────────┬─────────┘         │ - provenance checks │
                        │                         │                   └────────┬──────────┘
                        ▼                         ▼                            ▼
                  ┌─────────────┐        ┌──────────────────┐         ┌────────────────────────┐
                  │ MCP Agent   │        │ Analyst Console   │         │ MCP Tools (set_parameter│
                  │ Suggestions │        │ (review/confirm) │         │ _value, etc.)          │
                  └─────────────┘        └──────────────────┘         └────────────────────────┘
```

### Key Integration Points

- **Canonical schema** (Postgres/JSONB):
  ```json
  {
    "sourceId": "paper-2025-renal",
    "page": 4,
    "bbox": [120, 240, 380, 420],
    "type": "table",
    "context": "Table 2. Subject demographics",
    "fields": [
      {"name": "mean_body_weight", "value": 72.4, "unit": "kg", "confidence": 0.94},
      {"name": "dose_mg", "value": 40, "unit": "mg", "confidence": 0.9}
    ]
  }
  ```
- **Vector store**: embed paragraph text + table captions for semantic retrieval during QA or conversational queries.
- **Plot digitisation**: generate CSV + Matplotlib re-plot for visual verification; store alongside confidence score.
- **Agent hand-off**: build prompt templates that present the top-rated extracted fields and provenance before calling MCP tools.

## Security & Compliance Considerations

- Run PDF-Extract-Kit + OCR inside Kubernetes namespace with GPU nodes; enforce network policies so PDFs never leave the cluster by default.
- For cloud LLM calls, redact PHI and attach document hash to every request for auditability.
- Persist intermediate artefacts with retention policy to support scientific traceability; hash results for integrity checks.

## Implementation Roadmap

1. **Prototype (Sprint 1–2)**
   - Deploy PDF-Extract-Kit container with GPU support.
   - Parse curated corpus (≤10 PDFs) covering demographics + dosing tables.
   - Build comparison harness measuring table accuracy (precision/recall) vs. manual ground truth.
2. **LLM & Plot Integration (Sprint 3)**
   - Evaluate GPT-4o / Claude 3.5 for table clean-up and unit normalisation.
   - Implement PlotExtract-style pipeline for figure digitisation; store QA thumbnails.
3. **Schema & Storage (Sprint 4)**
   - Define canonical Postgres schema + PgVector index.
   - Implement ingestion service writing structured payloads + provenance.
4. **Agent Hook-up (Sprint 5)**
   - Expose REST endpoints (`/literature/extractions`, `/literature/extractions/{id}`).
   - Extend MCP agent prompts to surface extracted values with confirmation prompts.
5. **Evaluation Harness (Sprint 6)**
   - Assemble benchmark set with labeled fields.
   - Automate confidence scoring and reviewer UI for exception handling.

## Open Questions / Next Steps

- Select production OCR backbone (PaddleOCR vs. Tesseract + DocTR) based on GPU availability.
- Determine acceptable latency for analyst-in-the-loop vs. fully automated flows.
- Explore on-prem multimodal models (e.g., LLaVA 1.6, Llava-NeXT) as contingency if cloud GPT access is constrained.

## Mapping to MCP Actions

- `LiteratureActionMapper` aggregates extracted numeric fields and emits `set_parameter_value`
  suggestions including averaged values, provenance, and confirmation summaries.
- Field-to-parameter mappings are configurable; defaults cover body weight and oral dose, with
  keyword-based fallbacks for table columns.
- Returned `ActionSuggestion` objects slot directly into the LangGraph confirmation workflow so
  analysts can review supporting citations before committing changes.

## Evaluation Harness

- Fixtures: `tests/fixtures/literature/pdf_extract_kit_sample.pdf.json` (layout output) and
  `tests/fixtures/literature/gold_standard.json` (ground truth facts/tables).
- Pipeline execution + accuracy scoring exercised in
  `tests/unit/test_literature_evaluation.py`. Metrics currently reported:
  - `fact_accuracy`: fraction of extracted scalar fields within configured tolerances.
  - `table_row_recall`: proportion of expected table rows reproduced by extractors.
- `src/mcp_bridge/literature/evaluation.py` exposes reusable evaluation utilities so new
  fixtures/benchmarks can be added without rewriting tests or scripts.
