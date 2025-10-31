"""LLM client with PHI redaction and audit logging."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from ..audit import AuditTrail
from ..security.phi import PHIFilter, PHIFinding


class LLMTransport(Protocol):
    """Minimal synchronous transport interface for invoking an LLM."""

    def generate(self, prompt: str, **kwargs: Any) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class LLMResponse:
    prompt: str
    redacted_prompt: str
    output: str
    findings: list[PHIFinding]


class LLMClient:
    """Wraps an :class:`LLMTransport` with PHI redaction and audit logging."""

    def __init__(
        self,
        *,
        transport: LLMTransport,
        audit_trail: AuditTrail,
        redactor: PHIFilter | None = None,
    ) -> None:
        self._transport = transport
        self._audit = audit_trail
        self._redactor = redactor or PHIFilter()

    def generate(
        self,
        prompt: str,
        *,
        identity: Optional[Dict[str, Any]] = None,
        source_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        redacted_prompt, findings = self._redactor.redact(prompt)
        response = self._transport.generate(redacted_prompt, metadata=metadata or {})
        self._record_audit(
            prompt=prompt,
            redacted_prompt=redacted_prompt,
            findings=findings,
            identity=identity,
            source_hash=source_hash,
            metadata=metadata,
            response=response,
        )
        return LLMResponse(
            prompt=prompt,
            redacted_prompt=redacted_prompt,
            output=response,
            findings=findings,
        )

    # ------------------------------------------------------------------ #
    def _record_audit(
        self,
        *,
        prompt: str,
        redacted_prompt: str,
        findings: list[PHIFinding],
        identity: Optional[Dict[str, Any]],
        source_hash: Optional[str],
        metadata: Optional[Dict[str, Any]],
        response: str,
    ) -> None:
        if not getattr(self._audit, "enabled", False):  # pragma: no cover - audit disabled
            return

        def _digest(value: str) -> str:
            return hashlib.sha256(value.encode("utf-8")).hexdigest()

        finding_payload = [
            {
                "type": finding.type,
                "hash": _digest(finding.value),
                "start": finding.start,
                "end": finding.end,
            }
            for finding in findings
        ]

        payload: Dict[str, Any] = {
            "identity": identity,
            "llm": {
                "promptDigest": _digest(prompt),
                "redactedPromptDigest": _digest(redacted_prompt),
                "responseDigest": _digest(response),
                "sourceHash": source_hash,
                "metadata": metadata or {},
                "redacted": bool(findings),
                "findings": finding_payload,
            },
        }

        self._audit.record_event("llm.outbound", payload)


__all__ = ["LLMClient", "LLMResponse", "LLMTransport"]
