# Hardening Baseline

Date: 2026-04-23

This document records the current exposure model and the highest-value hardening findings confirmed in the repository. It is meant to keep future security and scientific-assurance work grounded in the actual implementation rather than generic concerns.

## Route exposure matrix

| Surface | Current policy | Notes |
| --- | --- | --- |
| `/health` | Public | Liveness only. Keep payload small and non-sensitive. |
| `/mcp/resources/schemas` | Public artifact | Published schema catalog intended for downstream validation. |
| `/mcp/resources/schemas/{schema_id}` | Public artifact | Public contract artifact. |
| `/mcp/resources/capability-matrix` | Public artifact | Public contract artifact. |
| `/mcp/resources/contract-manifest` | Public artifact | Public contract artifact. |
| `/mcp/resources/models` | Authenticated read | Reveals filesystem-backed model inventory and loaded-state hints. |
| `/mcp/resources/simulations` | Authenticated read | Reveals live session inventory. |
| `/mcp/resources/parameters` | Authenticated read | Reveals simulation structure and parameter metadata. |
| `/mcp/list_tools` | Authenticated read | Now filtered by caller role; anonymous dev mode sees viewer-safe tools only. |
| `/mcp/call_tool` | Authenticated by role | Critical tools still require explicit confirmation. |
| `/mcp` JSON-RPC | Authenticated after `initialize` and public contract resources | `initialize` remains unauthenticated transport negotiation; public `pbpk://` contract resources remain readable, while model/session/parameter resources match REST auth boundaries. |
| `/simulation/*` REST routes | Authenticated by role | Viewer/operator/admin separation already present on most routes. |
| `/audit/*` | Admin only | Audit log access remains privileged. |
| `/metrics` | Admin only | Prometheus payload is no longer implicitly public. |

## Confirmed repo risks that were real

1. Anonymous development mode previously mapped to `admin`, `operator`, and `viewer`, which erased the difference between "no identity" and "fully trusted identity".
2. Critical MCP tool confirmation was previously satisfied whenever anonymous mode was enabled, so a dev convenience flag weakened a core safety control.
3. The generic resource router exposed model inventories, simulation inventories, and parameter metadata without explicit auth policy.
4. `/metrics` and the previously bundled analyst console API had no explicit production-facing access policy in code.
5. The documented environment contract drifted from the runtime parser. Real examples in the repo used aliases such as `R_PATH`, `MCP_MODEL_SEARCH_PATHS`, `ADAPTER_TIMEOUT_SECONDS`, and `AUDIT_TRAIL_ENABLED` that the config model did not parse directly.
6. The default local compose profile published the anonymous-friendly service on all interfaces instead of binding it to localhost.

## Immediate hardening changes now present

1. Anonymous mode is reduced to viewer scope plus an `anonymous` marker role.
2. Critical MCP tool calls require explicit confirmation even when anonymous mode is enabled.
3. Sensitive resource routes now require authenticated read access, while public contract artifacts remain intentionally public.
4. `/metrics` is admin-only.
5. The analyst console surface is no longer shipped; retired `/console` and `/console/api/*` paths should remain absent in both local and production runtimes.
6. Anonymous-development responses now carry `X-PBPK-Security-Mode: anonymous-development` so local screenshots and demos are harder to mistake for production posture.
7. The config loader now accepts the legacy env names already used in docs and compose files, but emits warnings pointing operators toward the canonical names.
8. The default compose profile now binds `127.0.0.1:8000:8000` instead of all interfaces.
9. MCP streamable HTTP requests can enforce browser `Origin` allow-listing through `MCP_ALLOWED_ORIGINS`; absent `Origin` remains valid for CLI clients.
10. Hardened deployments can set `MCP_STRICT_TRANSPORT=true` to require the MCP `Accept` and `MCP-Protocol-Version` headers.

## Scientific-assurance findings that still need follow-through

1. The repo already tries to distinguish runtime capability, validation, executable verification, and scientific qualification, but these signals remain easy to detach from their surrounding caveats in downstream summaries.
2. The highest-value next steps are additive and local to the current contract: show scope, missing evidence, and misuse notes next to trust-bearing summaries before inventing many new schema families.
3. Work on "review dissent", "claim strength", or "decision blocks" should stay tied to existing outputs and real operator workflows; otherwise it risks creating a large governance surface without improving practical safety.

## Recommended sequencing

1. Keep the current security/config hardening track first.
2. Next, tighten trust-bearing summary language on existing outputs and reports.
3. Only then add new machine-readable scientific-assurance fields, and only where existing objects cannot carry the needed meaning.
