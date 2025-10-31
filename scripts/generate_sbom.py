#!/usr/bin/env python3
"""Generate a lightweight SBOM from the current Python environment.

The SBOM follows a simplified CycloneDX-style structure containing package name,
version, and detected license metadata. This avoids external tooling such as Syft
while still providing the minimum artefact required for compliance review.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from typing import Iterable, List, Optional


def _extract_license(dist: metadata.Distribution) -> Optional[str]:
    meta = dist.metadata
    license_value = meta.get("License")
    if license_value and license_value.strip():
        return license_value.strip()
    classifiers = meta.get_all("Classifier") or []
    licenses: List[str] = []
    for classifier in classifiers:
        if classifier.startswith("License ::"):
            licenses.append(classifier.split("::", maxsplit=1)[-1].strip())
    if licenses:
        return "; ".join(sorted(set(licenses)))
    return None


@dataclass
class Component:
    name: str
    version: str
    license: Optional[str]

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "library",
            "name": self.name,
            "version": self.version,
        }
        if self.license:
            payload["licenses"] = [{"license": {"name": self.license}}]
        else:
            payload["licenses"] = []
        return payload


def _discover_components() -> Iterable[Component]:
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        version = dist.version
        license_name = _extract_license(dist)
        yield Component(name=name, version=version, license=license_name)


def generate_sbom() -> dict[str, object]:
    components = sorted(
        (component.to_dict() for component in _discover_components()),
        key=lambda item: item["name"],
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{timestamp}",
        "metadata": {
            "timestamp": timestamp,
            "tools": [
                {
                    "vendor": "mcp-bridge",
                    "name": "generate_sbom.py",
                    "version": "1.0.0",
                }
            ],
        },
        "components": components,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SBOM JSON artefact.")
    parser.add_argument("output", help="Path to write the SBOM JSON file.")
    args = parser.parse_args()

    sbom = generate_sbom()
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(sbom, handle, indent=2, sort_keys=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
