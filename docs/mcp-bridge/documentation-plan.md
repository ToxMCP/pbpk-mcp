# MCP Bridge Documentation Plan & Information Architecture

## 1. Objectives

- Provide a cohesive documentation experience spanning architecture reference, day-to-day operator guides, and scientific workflows.
- Accelerate onboarding for two key personas:
  - **Agent developers / platform engineers** integrating the MCP bridge.
  - **PBPK scientists / power users** running simulations, sensitivity analyses, and population studies through agents or direct APIs.
- Establish a doc set that can evolve into an mkdocs/Read the Docs site without structural rework.

## 2. Documentation Pillars

| Pillar | Audience | Purpose | Existing Assets | Needed Additions |
| --- | --- | --- | --- | --- |
| **Quickstarts & Tutorials** | New users, scientists | Fast path from setup to first simulation / population run. | `README.md` (basic setup), `docs/tools/*.md`, `docs/mcp-bridge/getting-started/quickstart-cli.md`, `docs/mcp-bridge/getting-started/quickstart-agent.md` | Capture screenshots/plots, add dataset notes, expand tutorials for PK & sensitivity notebooks. |
| **Agent & Tooling Guides** | Agent developers | Explain LangGraph workflow, prompts, safety, tool semantics. | `docs/mcp-bridge/agent-usage.md`, `agent-prompts.md`, tool docs. | Confirm-before-execute sequence diagrams, troubleshooting, FAQ. |
| **API & Configuration Reference** | Platform engineers | Canonical schema, env vars, auth/audit controls. | `README.md` (env vars), `docs/mcp-bridge/contracts/`, `authentication.md`, `audit-trail.md`, `reference/api.md`, `reference/configuration.md`. | Automate OpenAPI export, add versioning policy, integrate into publishing pipeline. |
| **Scientific Workflows** | PBPK scientists | Reproduce end-to-end workloads: sensitivity, population, PK analytics. | `docs/mcp-bridge/sensitivity-analysis.md`, `population-simulation.md`. | Narrative tutorials, Jupyter notebooks, example datasets, expected runtimes. |
| **Operations & Release** | SREs, maintainers | Observe, benchmark, release safely. | `performance-plan.md`, `performance-profiling.md`, `performance-roadmap.md`, `threat-model.md`. | Troubleshooting runbook, release checklist, doc publishing SOP. |

## 3. Site Information Architecture

```
docs/
└── mcp-bridge/
    ├── getting-started/
    │   ├── quickstart-cli.md
    │   ├── quickstart-agent.md
    │   └── faq.md
    ├── workflows/
    │   ├── sensitivity-analysis.md (refactor existing)
    │   ├── population-simulation.md (augment with tutorial flow)
    │   └── pk-analytics.md (new, highlights report generation)
    ├── agent/
    │   ├── overview.md (from `agent-architecture.md`)
    │   ├── prompts.md (existing)
    │   └── operations.md (extend `agent-usage.md` with troubleshooting)
    ├── reference/
    │   ├── api.md (generated OpenAPI summary + sample payloads)
    │   ├── configuration.md (env var tables)
    │   ├── tools/
    │   │   ├── load_simulation.md (rename/move existing)
    │   │   └── …
    │   └── schemas/ (auto-exported JSON schemas)
    ├── operations/
    │   ├── performance.md (`performance-plan.md` + profiling digest)
    │   ├── audit-trail.md (existing)
    │   ├── authentication.md (existing)
    │   └── release-playbook.md (future Task 21 dependency)
    └── contribute/
        ├── style-guide.md
        └── publishing.md (CI docs & mkdocs instructions)
```

- Maintain `_index.md` style landing page summarising personas and entry points.
- Navigation groups: **Getting Started**, **Workflows**, **Agent**, **Reference**, **Operations**, **Contribute**.

## 4. Asset & Content Requirements

- **Quickstarts**: pair CLI + agent flows; embed snippet outputs; add diagrams produced via `mermaid`.
- **Notebooks**: staged under `docs/notebooks/` with Binder/nbviewer links; rely on fixtures in `tests/fixtures/` and benchmark datasets once `make fetch-bench-data` lands.
- **Media**: capture PNG plots for population / sensitivity outputs; store in `docs/assets/`.
- **Automation**:
  - `make docs-serve` / `make docs-build` targets using mkdocs-material.
  - GitHub Action to deploy docs on push to `main`.
  - Link checker via `mkdocs build --strict` or `lychee`.

## 5. Content Mapping for Task 20 Subtasks

| Subtask | Deliverables | Notes |
| --- | --- | --- |
| 20:1 (plan) | This document + nav tree; stakeholder sign-off. | Update as structure evolves; track TODOs. |
| 20:2 (tutorials) | `getting-started/quickstart-*.md`, refreshed workflow guides, embedded screenshots. | CLI + agent quickstarts drafted; next add media assets and extended PK/sensitivity notebooks. |
| 20:3 (reference) | `reference/api.md`, `reference/configuration.md`, refreshed OpenAPI schema. | Add automated export hook in mkdocs/CI to avoid drift. |
| 20:4 (demos) | Jupyter notebooks + demo scripts under `docs/notebooks/`; update README links. | Align dataset usage with benchmarks. |
| 20:5 (QA & publishing) | mkdocs config, CI automation, contribution guide. | Leverage `mkdocs-material`, `mkdocs-section-index`, `mkdocs-mermaid2`. |

## 6. Acceptance & Timeline

- **Blocking dependencies**: Task 15 outputs (population) already complete; docs must reference latest tool surface.
- **Milestones**:
  1. IA sign-off (current task).
  2. Quickstarts drafted & reviewed.
  3. Reference content synced with API.
  4. Notebooks verified in CI.
  5. Docs publishing workflow green.
- Aim for iterative PRs per milestone to avoid large doc diffs.

## 7. Open Questions

- Preferred hosting stack (GitHub Pages vs internal docs portal)?
- Are video assets required, or will animated GIFs suffice?
- Should we auto-generate tool docs from FastAPI route metadata to avoid drift?

> **Next action:** Kick off Subtask 20:2 by drafting quickstart outlines and sourcing screenshots/data assets.
