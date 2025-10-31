"""Schema validation utilities for literature extraction outputs."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Optional

from jsonschema import Draft202012Validator, ValidationError

from .models import ExtractionRecord, LiteratureExtractionResult

_SCHEMA_ENV_VAR = "MCP_BRIDGE_EXTRACTION_SCHEMA"
_SCHEMA_FILENAME = "extraction-record.json"


class ExtractionSchemaError(ValueError):
    """Raised when an extraction record fails schema validation."""


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / _SCHEMA_FILENAME


def _load_schema(schema_path: Optional[str]) -> dict[str, Any]:
    explicit = schema_path or os.getenv(_SCHEMA_ENV_VAR)
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"Extraction schema not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    default_path = _default_schema_path()
    if default_path.is_file():
        return json.loads(default_path.read_text(encoding="utf-8"))

    try:
        schema_pkg = resources.files("mcp_bridge.schemas").joinpath(_SCHEMA_FILENAME)
    except AttributeError:  # pragma: no cover - importlib fallback compat
        schema_pkg = None

    if schema_pkg and schema_pkg.is_file():
        with schema_pkg.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    raise FileNotFoundError(
        "Extraction schema not found. Set MCP_BRIDGE_EXTRACTION_SCHEMA to the schema path."
    )


class ExtractionSchemaValidator:
    """Validate extraction records against the canonical JSON Schema."""

    def __init__(self, schema_path: Optional[str] = None) -> None:
        self._schema = _load_schema(schema_path)
        self._validator = Draft202012Validator(self._schema)

    def validate_record(self, record: ExtractionRecord) -> None:
        payload = record.model_dump(mode="json")
        try:
            self._validator.validate(payload)
        except ValidationError as exc:
            raise ExtractionSchemaError(str(exc)) from exc

    def validate_records(self, records: Iterable[ExtractionRecord]) -> None:
        for record in records:
            self.validate_record(record)

    def validate_result(self, result: LiteratureExtractionResult) -> None:
        self.validate_records(result.records)


default_validator = ExtractionSchemaValidator()
