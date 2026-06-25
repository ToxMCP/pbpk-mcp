"""Blocking-failure model + meta fail-closed codes for the Track-B gate.

A ``BlockingFinding`` is the uniform shape the gate aggregates and that turns the
exit code non-zero. Two families of codes flow through it:

* SCIENTIFIC codes emitted by the vendored spine policy engine itself
  (e.g. ``BER_NOT_RISK_OR_REGULATORY``, ``AI_MODEL_IDENTITY_REQUIRED``). These
  are passed through verbatim from the engine's ``failures[]``.

* META fail-closed codes synthesized by the *bridge* when it cannot trust the
  engine's verdict (engine missing/crashed/timed out, unrecognized schemaId,
  vendored-file tamper) or by the *projection* when it cannot faithfully map a
  source object. Every one of these BLOCKS — none is ever downgraded to a pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- META fail-closed codes (synthesized, never from the engine) -------------

#: Node missing / non-zero exit / empty or unparseable stdout / timeout.
ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"

#: The projected object's schemaId is not in the engine's recognized set, so a
#: ``valid:true`` from the engine would be a silent no-op. Treated as blocking.
UNRECOGNIZED_SPINE_SCHEMA_ID = "UNRECOGNIZED_SPINE_SCHEMA_ID"

#: A vendored engine file's sha256 does not match VENDORED_FROM.json (tamper).
VENDOR_DIGEST_MISMATCH = "VENDOR_DIGEST_MISMATCH"

#: The projection could not faithfully map a required field / unmapped enum.
PROJECTION_INCOMPLETE = "PROJECTION_INCOMPLETE"

#: The raw source packet failed the producer's STRICT emission contract
#: (additionalProperties:false JSON schema / .strict() Zod) — validated BEFORE any
#: projection. Blocks; the packet is never projected. This guard closes the
#: producer-emission-contract dead-arm class: a "fault" that can only fire a
#: scientific code by carrying a schema-forbidden / undeclared field (or by
#: hand-mutating a CONSTANT the projection synthesizes) is caught here as a
#: contract violation instead of silently advertising a code that never bites on a
#: real producer-emitted packet. (Code constant lives in source_contract.py's
#: __all__ re-export too; defined here to avoid an import cycle.)
SOURCE_CONTRACT_VIOLATION = "SOURCE_CONTRACT_VIOLATION"

#: Every meta code, for gate aggregation / documentation.
META_FAIL_CLOSED_CODES: frozenset[str] = frozenset(
    {
        ENGINE_UNAVAILABLE,
        UNRECOGNIZED_SPINE_SCHEMA_ID,
        VENDOR_DIGEST_MISMATCH,
        PROJECTION_INCOMPLETE,
        SOURCE_CONTRACT_VIOLATION,
    }
)


@dataclass(frozen=True)
class BlockingFinding:
    """One release-blocking finding (scientific or meta fail-closed)."""

    code: str
    message: str
    path: str = "$"
    #: "scientific" (from the engine) or "meta" (synthesized fail-closed).
    origin: str = "scientific"
    #: Free-form context (the source object id, the projected schemaId, etc.).
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "origin": self.origin,
            "context": dict(self.context),
        }

    @classmethod
    def meta(cls, code: str, message: str, **context: Any) -> BlockingFinding:
        return cls(code=code, message=message, origin="meta", context=context)


class ProjectionIncompleteError(Exception):
    """Raised by the projection when a source object cannot be faithfully mapped.

    The gate catches this and records a ``PROJECTION_INCOMPLETE`` blocking
    finding — a missing required field or unmapped enum is NEVER silently
    defaulted to a safe branch.
    """

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(message)
        self.message = message
        self.path = path
