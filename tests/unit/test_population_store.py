"""Tests for the population result storage implementation."""

from __future__ import annotations

import json
import os
import time

import pytest

from mcp_bridge.storage.population_store import (
    PopulationResultStore,
    PopulationStorageError,
)


def test_store_and_load_chunk(tmp_path) -> None:
    store = PopulationResultStore(tmp_path)
    payload = {"chunkId": "chunk-1", "values": [1, 2, 3]}

    stored = store.store_json_chunk("pop-123", "chunk-1", payload)
    assert stored.uri.endswith("/chunks/chunk-1")
    assert stored.size_bytes > 0

    metadata = store.get_metadata("pop-123", "chunk-1")
    assert metadata.size_bytes == stored.size_bytes

    with store.open_chunk("pop-123", "chunk-1") as stream:
        loaded = json.load(stream)
    assert loaded == payload


def test_invalid_identifier_rejected(tmp_path) -> None:
    store = PopulationResultStore(tmp_path)
    with pytest.raises(PopulationStorageError):
        store.store_json_chunk("../bad", "chunk-1", {})


def test_purge_expired_results(tmp_path) -> None:
    store = PopulationResultStore(tmp_path)
    store.store_json_chunk("pop-old", "chunk-1", {"values": [1]})
    store.store_json_chunk("pop-new", "chunk-1", {"values": [2]})

    old_dir = tmp_path / "pop-old"
    new_dir = tmp_path / "pop-new"
    assert old_dir.exists() and new_dir.exists()

    past = time.time() - 3600
    os.utime(old_dir, (past, past))
    os.utime(old_dir / "chunk-1.json", (past, past))

    removed = store.purge_expired(1800)
    assert removed == 1
    assert not old_dir.exists()
    assert new_dir.exists()
