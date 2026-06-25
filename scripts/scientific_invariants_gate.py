#!/usr/bin/env python3
"""Track-B scientific-invariants gate (vendored schema-spine engine) for pbpk-mcp.

Projects the RELEASED ``pbpkQualificationSummary.v1`` (the anti-overclaim
governance seam — a PBPK simulation qualification is NOT a validated regulatory
dose, and a screening-tier PBK output is NOT externally-validated PBPK /
risk-regulatory decision support) onto its canonical ToxMCP schema-spine
``InternalExposureSummary`` shape, runs the vendored, digest-pinned spine policy
engine over the projection via a fail-closed Python bridge, aggregates every
blocking finding, and EXITS NON-ZERO if any public-release-blocking code fires.

pbpk-mcp's released objects are produced by DETERMINISTIC builders
(``_build_pbpk_qualification_summary`` in
``src/mcp_bridge/pbpk_tools/ingest_external_pbpk_bundle.py``) that already encode
these anti-overclaim postures natively (decisionBoundary no-ngra-decision-policy,
supports.regulatoryDecision false, workflowClaimBoundaries.directRegulatoryDose
Derivation not-supported, export-block + caution summaries), so on the PRISTINE
corpus this gate is GREEN. Its job is to BLOCK if a future change ever lets one of
these regressions into a released qualification summary:

  Scientific (from the engine), the ADVERTISED set — every one re-proven to bite on
  a PRODUCER-CONTRACT-VALID summary fault, each plumbed from a DECLARED producer
  field (see docs/governance/adr/0001-track-b-scientific-invariants-gate.md and
  tests/governance/test_scientific_invariants_adversarial.py):
    HTTK_SCREENING_NOT_PBPK                          <- qualificationLevel/oecdReadiness
                                                        + riskAssessmentReady + supports.*
    INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY   <- supports.regulatoryDecision
                                                        + workflowClaimBoundaries
    INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED           <- performanceEvidenceBoundary
                                                        + limitations + requiredExternalInputs

  Meta fail-closed (synthesized by the source-contract guard / bridge / projection):
    SOURCE_CONTRACT_VIOLATION, ENGINE_UNAVAILABLE, UNRECOGNIZED_SPINE_SCHEMA_ID,
    VENDOR_DIGEST_MISMATCH, PROJECTION_INCOMPLETE

HONEST N/A (see ADR-0001):
  * INTERNAL_EXPOSURE_BASIS_REQUIRED dispatches on route/matrix/bindingBasis
    "not_assessed". The pbpkQualificationSummary declares NONE of route / matrix /
    binding-basis (those live on the SEPARATE internalExposureEstimate.v1 object),
    so projecting one as a mutable driver would be a SYNTHESIZED dead arm. The
    projection stamps fixed faithful substrate values and the gate does NOT
    advertise that code.
  * AI-provenance arm: pbpk-mcp's released objects are deterministic; the only LLM
    (src/mcp_bridge/services/llm.py) has NO callers in src/ and feeds NO released
    object. The gate projects no AssessmentRun and advertises no AI code; the
    deterministic N/A + re-introduction path are documented in the ADR.

This gate is ADVISORY on the free-plan repo (no required-status-checks). PROMOTE-
TO-BLOCKING: when the repo gains branch protection / rulesets, mark the
``scientific-invariants`` CI job a required status check — the gate already exits
non-zero on any blocking code. It is ADDITIVE: it touches no PBPK src/, no
schemas/, no contract artifacts, and does NOT dispatch or modify the
release-artifacts / model-smoke workflows, so those gates are untouched.

Exit codes:
    0 — every projected object passed the engine (no blocking code fired)
    1 — at least one blocking code fired (release-blocking regression)
    2 — usage / corpus-loading error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from governance import project_to_spine as projector  # noqa: E402
from governance import source_contract  # noqa: E402
from governance import spine_bridge as bridge  # noqa: E402
from governance.errors import (  # noqa: E402
    PROJECTION_INCOMPLETE,
    BlockingFinding,
    ProjectionIncompleteError,
)

# --- corpus ------------------------------------------------------------------
# Each entry: (relative path, projection kind). The gate FAILS (exit 2) if a
# declared corpus file is missing, so the corpus cannot silently shrink.

PBPK_QUALIFICATION_SUMMARY = "pbpk_qualification_summary"

DEFAULT_CORPUS: tuple[tuple[str, str], ...] = (
    # The authentic, FULL producer-emitted pbpkQualificationSummary, captured by
    # running the real producer (_build_pbpk_qualification_summary over a clean
    # external PBPK qualification bundle). Regenerate via
    # scripts/build_spine_projection_goldens.py.
    ("governance/fixtures/pbpk-qualification-summary.pristine.json", PBPK_QUALIFICATION_SUMMARY),
)

# The advertised public-release-blocking scientific codes — the MAXIMAL set that
# bites on a PRODUCER-CONTRACT-VALID source fault (jsonschema-valid against the
# strict emission contract -> a real engine exit through this gate), each plumbed
# from a DECLARED producer field. No over-advertise, no dead arms. (Meta codes from
# errors.META_FAIL_CLOSED_CODES are ALWAYS blocking and need no listing.)
BLOCKING_SCIENTIFIC_CODES: frozenset[str] = frozenset(
    {
        "HTTK_SCREENING_NOT_PBPK",
        "INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY",
        "INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED",
    }
)


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _project(kind: str, source: dict[str, Any], rel: str) -> list[tuple[str, dict[str, Any]]]:
    if kind == PBPK_QUALIFICATION_SUMMARY:
        return projector.project_qualification_summary(source, object_label=rel)
    raise ProjectionIncompleteError(f"Unknown projection kind {kind!r}.")


def run_gate(corpus: list[tuple[str, str]], *, emit_json: bool = False) -> int:
    findings: list[tuple[str, BlockingFinding]] = []
    checked = 0
    for rel, kind in corpus:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"[scientific-invariants] FAIL: corpus file missing: {rel}", file=sys.stderr)
            return 2
        source = _load(path)

        # SOURCE-CONTRACT GUARD (fail-closed, BEFORE any projection). A packet that
        # violates the producer's STRICT emission contract (the
        # additionalProperties:false tightening of the producer dict builder)
        # BLOCKS and is NEVER projected — so a "fault" that could only fire a
        # scientific code by carrying a schema-forbidden / undeclared field (or an
        # out-of-enum value the producer cannot emit) is caught here as a contract
        # violation instead of silently exercising a dead arm.
        contract_violation = source_contract.validate_source_packet(
            source, kind=kind, corpus=rel
        )
        if contract_violation is not None:
            findings.append((rel, contract_violation))
            continue

        try:
            projected = _project(kind, source, rel)
        except ProjectionIncompleteError as exc:
            findings.append(
                (
                    rel,
                    BlockingFinding.meta(
                        PROJECTION_INCOMPLETE, exc.message, path=exc.path, corpus=rel
                    ),
                )
            )
            continue

        for label, obj in projected:
            checked += 1
            result = bridge.validate_object(obj)
            for finding in result.findings:
                findings.append((label, finding))

    # SAFE-BY-DEFAULT: every meta finding blocks, AND every scientific finding
    # blocks (a scientific code the engine emits over a projected object is, by
    # construction, a real invariant violation). The advertised allowlist above is
    # documentation; we do not silently drop an unlisted engine code.
    blocking = [(label, f) for (label, f) in findings]

    if emit_json:
        print(
            json.dumps(
                {
                    "checkedObjects": checked,
                    "advertisedCodes": sorted(BLOCKING_SCIENTIFIC_CODES),
                    "blocking": [
                        {"object": label, **f.as_dict()} for (label, f) in blocking
                    ],
                    "allFindings": [
                        {"object": label, **f.as_dict()} for (label, f) in findings
                    ],
                },
                indent=2,
            )
        )

    if blocking:
        print(
            f"[scientific-invariants] BLOCK — {len(blocking)} release-blocking "
            f"finding(s) across {checked} projected object(s):",
            file=sys.stderr,
        )
        for label, f in blocking:
            print(f"  - [{f.origin}] {f.code} @ {label} {f.path}: {f.message}", file=sys.stderr)
        return 1

    print(
        f"[scientific-invariants] OK — {checked} projected object(s) passed the "
        f"vendored spine policy engine (no release-blocking code fired).",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report to stdout.",
    )
    args = parser.parse_args(argv)
    return run_gate(list(DEFAULT_CORPUS), emit_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
