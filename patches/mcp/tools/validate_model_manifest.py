"""MCP tool for static validation of PBPK model manifests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.model_manifest import validate_model_manifest as validate_manifest_payload

from .load_simulation import resolve_model_path

TOOL_NAME = "validate_model_manifest"
CONTRACT_VERSION = "pbpk-mcp.v1"


class ValidateModelManifestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    file_path: str = Field(alias="filePath", min_length=1)


class ValidateModelManifestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    file_path: str = Field(alias="filePath")
    backend: str
    runtime_format: str = Field(alias="runtimeFormat")
    manifest: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_manifest(cls, payload: Mapping[str, Any]) -> "ValidateModelManifestResponse":
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
            filePath=str(payload.get("filePath")),
            backend=str(payload.get("backend")),
            runtimeFormat=str(payload.get("runtimeFormat")),
            manifest=dict(payload.get("manifest") or {}),
        )


def validate_model_manifest(payload: ValidateModelManifestRequest) -> ValidateModelManifestResponse:
    resolved = resolve_model_path(payload.file_path)
    manifest_payload = validate_manifest_payload(Path(resolved))
    return ValidateModelManifestResponse.from_manifest(manifest_payload)


__all__ = [
    "ValidateModelManifestRequest",
    "ValidateModelManifestResponse",
    "validate_model_manifest",
]
