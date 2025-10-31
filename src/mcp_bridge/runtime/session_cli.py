"""Utility CLI for inspecting and managing the session registry."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mcp.session_registry import RedisSessionRegistry, SessionRegistry, SessionRegistryError, set_registry

from ..config import load_config
from .factory import build_session_registry


def _load_registry() -> SessionRegistry | RedisSessionRegistry:
    config = load_config()
    registry = build_session_registry(config)
    set_registry(registry)
    return registry


def _cmd_dump(args: argparse.Namespace) -> int:
    registry = _load_registry()
    snapshot = registry.snapshot()
    payload: list[dict[str, Any]] = []
    for record in snapshot:
        payload.append(
            {
                "simulationId": record.handle.simulation_id,
                "filePath": record.handle.file_path,
                "metadata": record.metadata,
                "createdAt": record.created_at,
                "lastAccessed": record.last_accessed,
            }
        )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent)
    if indent is not None:
        sys.stdout.write("\n")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:  # noqa: ARG001 - interface requirement
    registry = _load_registry()
    removed = registry.prune_stale_entries()
    if removed:
        print(f"Removed {len(removed)} stale session(s): {', '.join(sorted(removed))}")
    else:
        print("No stale sessions detected")
    return 0


def _cmd_clear(args: argparse.Namespace) -> int:
    if not args.force:
        print("--force flag required to clear the session registry", file=sys.stderr)
        return 2
    registry = _load_registry()
    registry.clear()
    print("Session registry cleared")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Session registry tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dump_parser = subparsers.add_parser("dump", help="Print active sessions as JSON")
    dump_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    dump_parser.set_defaults(func=_cmd_dump)

    prune_parser = subparsers.add_parser(
        "prune-stale", help="Remove registry entries whose backing records have expired"
    )
    prune_parser.set_defaults(func=_cmd_prune)

    clear_parser = subparsers.add_parser("clear", help="Delete all session records")
    clear_parser.add_argument("--force", action="store_true", help="Acknowledge destructive action")
    clear_parser.set_defaults(func=_cmd_clear)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SessionRegistryError as exc:
        parser.error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard
        parser.error(f"Unexpected error: {exc}")
    return 1


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
