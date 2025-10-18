"""Filesystem-backed storage for population simulation outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO


class PopulationStorageError(RuntimeError):
    """Base error raised for population storage operations."""


class PopulationChunkNotFoundError(PopulationStorageError):
    """Raised when a requested population chunk cannot be located."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class StoredChunk:
    """Metadata describing a stored population chunk."""

    results_id: str
    chunk_id: str
    uri: str
    path: Path
    size_bytes: int
    content_type: str = "application/json"


class PopulationResultStore:
    """Persist population simulation artefacts using a claim-check pattern."""

    def __init__(self, base_path: str | Path, *, uri_prefix: str = "/population_results") -> None:
        base = Path(base_path).expanduser()
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
        base.mkdir(parents=True, exist_ok=True)
        self._base_path = base
        self._uri_prefix = uri_prefix.rstrip("/") or "/population_results"

    @property
    def base_path(self) -> Path:
        return self._base_path

    def store_json_chunk(self, results_id: str, chunk_id: str, payload: Any) -> StoredChunk:
        safe_results_id = self._validate_identifier(results_id, "results_id")
        safe_chunk_id = self._validate_identifier(chunk_id, "chunk_id")
        target_dir = self._base_path / safe_results_id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{safe_chunk_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        temp_path.replace(path)
        size = path.stat().st_size
        uri = f"{self._uri_prefix}/{safe_results_id}/chunks/{safe_chunk_id}"
        return StoredChunk(
            results_id=safe_results_id,
            chunk_id=safe_chunk_id,
            uri=uri,
            path=path,
            size_bytes=size,
        )

    def get_metadata(self, results_id: str, chunk_id: str) -> StoredChunk:
        safe_results_id = self._validate_identifier(results_id, "results_id")
        safe_chunk_id = self._validate_identifier(chunk_id, "chunk_id")
        path = self._chunk_path(safe_results_id, safe_chunk_id)
        if not path.is_file():
            raise PopulationChunkNotFoundError(
                f"Chunk '{chunk_id}' for results '{results_id}' was not found"
            )
        size = path.stat().st_size
        uri = f"{self._uri_prefix}/{safe_results_id}/chunks/{safe_chunk_id}"
        return StoredChunk(
            results_id=safe_results_id,
            chunk_id=safe_chunk_id,
            uri=uri,
            path=path,
            size_bytes=size,
        )

    def open_chunk(self, results_id: str, chunk_id: str) -> BinaryIO:
        metadata = self.get_metadata(results_id, chunk_id)
        return metadata.path.open("rb")

    def delete_results(self, results_id: str) -> None:
        safe_results_id = self._validate_identifier(results_id, "results_id")
        directory = self._base_path / safe_results_id
        if not directory.exists():
            return
        for path in directory.glob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)
        directory.rmdir()

    def _chunk_path(self, results_id: str, chunk_id: str) -> Path:
        return self._base_path / results_id / f"{chunk_id}.json"

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> str:
        if not _IDENTIFIER_RE.match(value):
            raise PopulationStorageError(f"Invalid {field_name} '{value}'")
        return value


__all__ = [
    "PopulationChunkNotFoundError",
    "PopulationResultStore",
    "PopulationStorageError",
    "StoredChunk",
]
