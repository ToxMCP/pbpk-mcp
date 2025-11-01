"""Minimal JWT helpers used when python-jose is unavailable."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Iterable


class JWTError(Exception):
    """Raised when JWT encoding/decoding fails."""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class SimpleJWT:
    def encode(self, payload: dict[str, Any], key: str, algorithm: str = "HS256") -> str:
        if algorithm != "HS256":
            raise NotImplementedError("Only HS256 is supported in simple JWT implementation")
        header = {"typ": "JWT", "alg": algorithm}
        segments = [
            _b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        ]
        signing_input = ".".join(segments).encode("utf-8")
        signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        segments.append(_b64encode(signature))
        return ".".join(segments)

    def decode(
        self,
        token: str,
        key: str,
        algorithms: Iterable[str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        algorithms = list(algorithms or ["HS256"])
        if "HS256" not in algorithms:
            raise NotImplementedError("Only HS256 is supported in simple JWT implementation")
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError as exc:
            raise JWTError("Invalid token format") from exc

        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_signature = _b64decode(signature_b64)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise JWTError("Signature verification failed")

        payload = json.loads(_b64decode(payload_b64))
        return payload


jwt = SimpleJWT()
