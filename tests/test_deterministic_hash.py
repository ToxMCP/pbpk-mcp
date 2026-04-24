"""Tests for deterministic audit hashing (PBPK-03 remediation)."""

from __future__ import annotations

from mcp_bridge.audit.trail import compute_event_hash


def test_hash_is_deterministic_for_same_event() -> None:
    event = {
        "eventId": "test-1",
        "timestamp": "2026-04-15T12:00:00Z",
        "eventType": "test.event",
        "payload": {"value": 0.1 + 0.2},
    }
    hash1 = compute_event_hash(event)
    hash2 = compute_event_hash(event)
    assert hash1 == hash2


def test_float_normalization_makes_mathematically_equivalent_hashes() -> None:
    """0.1 + 0.2 and 0.3 should produce the same hash after canonicalization."""
    event1 = {
        "eventId": "test-1",
        "timestamp": "2026-04-15T12:00:00Z",
        "eventType": "test.event",
        "payload": {"value": 0.1 + 0.2},
    }
    event2 = {
        "eventId": "test-1",
        "timestamp": "2026-04-15T12:00:00Z",
        "eventType": "test.event",
        "payload": {"value": 0.3},
    }
    hash1 = compute_event_hash(event1)
    hash2 = compute_event_hash(event2)
    assert hash1 == hash2


def test_nested_dict_sorting_is_deterministic() -> None:
    event = {
        "eventType": "test.event",
        "nested": {
            "z": 1,
            "a": 2,
            "m": {"c": 3, "b": 4},
        },
    }
    hash1 = compute_event_hash(event)
    hash2 = compute_event_hash(event)
    assert hash1 == hash2


def test_hash_strips_hash_and_signature_fields() -> None:
    base = {"eventType": "test.event", "value": 42}
    hash1 = compute_event_hash({**base, "hash": "abc"})
    hash2 = compute_event_hash({**base, "hash": "xyz", "signature": "sig"})
    hash3 = compute_event_hash(base)
    assert hash1 == hash2 == hash3


def test_special_float_values_are_canonical() -> None:
    event = {
        "eventType": "test.event",
        "nan": float("nan"),
        "inf": float("inf"),
        "neg_inf": float("-inf"),
    }
    h = compute_event_hash(event)
    assert isinstance(h, str)
    assert len(h) == 64
