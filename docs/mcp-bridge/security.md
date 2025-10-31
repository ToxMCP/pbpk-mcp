# Security Controls

## PHI redaction

- All outbound LLM prompts pass through `PHIFilter`, which masks sensitive tokens (SSNs, MRNs, phone numbers, emails, DOB) before transmission.
- The LLM client writes `llm.outbound` audit events capturing:
  - prompt and response digests
  - whether redaction occurred and the hashed findings (pattern only, no raw PHI)
  - caller identity and optional `sourceHash` provenance tag (e.g., originating document hash)
- Agents should populate `sourceHash` when invoking the LLM client so evidence can be traced back to the underlying dataset.

## Idempotency & audit correlation

- MCP tool invocations emit `tool.<name>` audit events with argument digests, idempotency keys, and result summaries.
- Duplicate tool calls using the same idempotency key reuse the first job; mismatched payloads are rejected with HTTP 409.

Refer to `docs/mcp-bridge/audit-trail.md` for full event schemas and verification workflow.
