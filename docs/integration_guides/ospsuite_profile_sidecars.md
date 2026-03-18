# OSPSuite Profile Sidecars

## Purpose

OSPSuite transfer files (`.pkml`) do not carry the richer OECD-style scientific profile metadata that the MCP now exposes for `rxode2` models.

To attach project-specific scientific metadata to a `.pkml` model without modifying the transfer file itself, the bridge supports optional JSON sidecar files.

## Supported Sidecar Names

For a model path such as:

```text
/app/var/models/example/Pregnant_simulation_PKSim.pkml
```

the bridge checks, in order:

```text
/app/var/models/example/Pregnant_simulation_PKSim.profile.json
/app/var/models/example/Pregnant_simulation_PKSim.pbpk.json
/app/var/models/example/Pregnant_simulation_PKSim.pkml.profile.json
```

The first existing file is used.

## Payload Shape

The sidecar may be either:

- a direct profile object, or
- an object with a top-level `profile` field

Supported sections mirror the current MCP scientific profile structure:

- `contextOfUse`
- `applicabilityDomain`
- `uncertainty`
- `implementationVerification`
- `peerReview`

Unspecified sections fall back to the bridge defaults for OSPSuite `.pkml` models.

## Behavior

When a sidecar is found:

- `load_simulation` returns the merged `profile`
- `capabilities.scientificProfile` becomes `true`
- `capabilities.applicabilityDomain` mirrors the merged profile domain
- `profile.profileSource.type` is set to `sidecar`
- `validate_simulation_request` can compare a requested context of use or domain hint against the declared sidecar metadata before execution
- `validation.assessment.oecdChecklist` reports per-dimension OECD-style metadata coverage
- `validation.assessment.oecdChecklistScore` summarizes that coverage numerically

When a `.pkml` file declares an empty `OutputSelections` block:

- the bridge keeps the declared scientific/profile metadata unchanged
- `load_simulation` emits a warning explaining that runtime outputs were auto-seeded
- `capabilities.outputSelectionMode` is set to `observer-fallback`
- a bounded observer-based output set is selected so deterministic execution can proceed

When no sidecar is found:

- the bridge returns the OSPSuite default profile
- `capabilities.scientificProfile` remains `false`
- `profile.profileSource.type` is `bridge-default`

## Example

This workspace includes an example sidecar for:

```text
var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml
```

at:

```text
var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.profile.json
```

That example is intentionally conservative and now carries model-specific scope statements, such as route, species, or example-model status where those can be inferred safely from the transfer file and filename. It still does not imply a formal qualification package.

## Curated Workspace Set

The current workspace now ships sidecars for the curated profile/example models:

- `var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml`
- `var/models/esqlabs/PBPK-for-cross-species-extrapolation/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rat.pkml`
- `var/models/esqlabs/TissueTMDD/repeated dose model.pkml`
- `var/models/esqlabs/esqlabsR/simple.pkml`

These sidecars are intentionally conservative, but they are no longer generic `demo-only` placeholders. They now distinguish illustrative scientific examples from pure integration fixtures and encode the strongest scope statement that can be supported from the workspace artifacts alone. They still do not claim formal scientific qualification.
