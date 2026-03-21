# Capability Matrix

This matrix is the adoption-facing summary of what the current public PBPK MCP contract supports for each input class.

Machine-readable source of truth:

- `docs/architecture/capability_matrix.json`

Status meaning:

- `Yes` means the published workflow supports the operation directly.
- `Conditional` means support depends on the model declaring the needed runtime capability.
- `No` means the operation is outside the published workflow for that input class.

| Input class | Discovery | Static manifest | Load | Request validation | Verification | Deterministic run | Population run | Dossier export | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PK-Sim / MoBi `.pkml` | Yes | Yes | Yes | Yes | Yes | Yes | No | Yes | Runtime backend is `ospsuite`; sidecars can enrich qualification metadata. |
| Contract-complete MCP-ready `.R` | Yes | Yes | Yes | Yes | Yes | Yes | Conditional | Yes | Runtime backend is `rxode2`; population support depends on declared model capability. |
| Discoverable but incomplete `.R` | Yes | Yes | No | No | No | No | No | No | Appears in discovery, but must satisfy the PBPK MCP hook contract before runtime use. |
| PK-Sim project `.pksim5` | No | No | No | No | No | No | No | No | Conversion-only; export to `.pkml` first. |
| Berkeley Madonna `.mmd` | No | No | No | No | No | No | No | No | Conversion-only; convert to `.pkml` or MCP-ready `.R` first. |

Operational boundaries behind the matrix:

- `discover_models` and `/mcp/resources/models` only expose supported runtime formats, currently `.pkml` and `.R`.
- `validate_model_manifest` is the intended pre-load curation surface for both supported runtime formats.
- `run_population_simulation` and `get_population_results` are public tools, but their current backend support is intentionally narrower than deterministic execution.
- Conversion-only inputs are rejected with actionable messages rather than being silently coerced into runtime behavior.

This matrix is intentionally about the public contract, not about every file the repository may contain internally.
