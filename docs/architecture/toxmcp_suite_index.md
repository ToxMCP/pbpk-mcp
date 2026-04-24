# ToxMCP Suite Index

This is the shortest public-facing map of the current ToxMCP service family from
the PBPK MCP point of view.

Use it to answer three questions quickly:

1. Which MCP owns this scientific question?
2. Which service should provide the upstream handoff?
3. Which sibling service should consume the next output?

## Current Service Map

| Service | Primary role | Current status |
| --- | --- | --- |
| `Direct-Use Exposure MCP` | Deterministic direct-use and near-field external-dose construction, evidence reconciliation, bounded worker screening, PBPK-ready handoff packaging | Released |
| `PBPK MCP` | Toxicokinetic simulation, internal-dose translation, qualification, and dossier export | Released sibling |
| `Bioactivity-PoD MCP` | Bioactivity normalization, PoD derivation, backend governance, and downstream qualification evidence | Sibling service |
| `ToxClaw` | Cross-service orchestration, refinement policy, case assembly, and reporting | Sibling orchestrator |
| `Fate MCP` | Environmental release, multimedia transfer, concentration surfaces | Planned sibling |
| `Dietary MCP` | Commodity residues, food-consumption mappings, dietary oral intake | Planned sibling |
| `Literature MCP` | Source normalization, extraction review, evidence-pack curation | Optional future sibling |

## Fast Routing Table

- Internal dose, simulation, qualification, or PBPK dossier question -> `PBPK MCP`
- External exposure scenario or direct-use worker screening question -> `Direct-Use Exposure MCP`
- Bioactivity fitting or PoD derivation question -> `Bioactivity-PoD MCP`
- Environmental release or multimedia concentration question -> `Fate MCP`
- Dietary oral intake or food-residue question -> `Dietary MCP`
- Integrated case assembly, refinement choice, or final NGRA-facing reporting question -> `ToxClaw`

## Cross-MCP Handoff Pattern

- `Direct-Use Exposure MCP` provides external-dose and scenario context.
- `Bioactivity-PoD MCP` provides PoD-side and review-side context.
- `PBPK MCP` consumes external exposure and PoD references, then emits internal-dose and qualification outputs without claiming upstream ownership.
- `ToxClaw` stays responsible for cross-service synthesis and final case reporting.

## Read This Repo In Order

1. [README](../../README.md)
2. [Capability Matrix](./capability_matrix.md)
3. [Exposure-led NGRA Role](./exposure_led_ngra_role.md)
4. [Dual-backend architecture](./dual_backend_pbpk_mcp.md)
5. [Release notes](../releases/v0.5.0.md)

## Public Companions

- `docs/architecture/toxmcp_suite_index.md`
- `/mcp/resources/capability-matrix`
- `/mcp/resources/contract-manifest`
- `/mcp/resources/release-bundle-manifest`
