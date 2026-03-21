#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from importlib import metadata


REQUIRED_MODULES = (
    ("build", "sdist and wheel distribution smoke build"),
    ("pydantic", "runtime schema-backed tool models"),
    ("jsonschema", "published contract schema validation"),
)


def main() -> int:
    missing: list[tuple[str, str]] = []
    versions: dict[str, str] = {}

    for module_name, purpose in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
            versions[module_name] = metadata.version(module_name)
        except Exception:
            missing.append((module_name, purpose))

    if missing:
        print("Runtime contract environment check failed.", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "The following dependencies are required so the published PBPK contract tests run without skips:",
            file=sys.stderr,
        )
        for module_name, purpose in missing:
            print(f"- {module_name}: {purpose}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Install the project dependencies first, for example with `python -m pip install -e '.[dev]'`.",
            file=sys.stderr,
        )
        return 1

    print("Runtime contract environment check passed.")
    for module_name in sorted(versions):
        print(f"- {module_name} {versions[module_name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
