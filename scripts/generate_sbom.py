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
from pathlib import Path
from typing import Iterable, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10
    import tomli as tomllib  # type: ignore[no-redef]


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


def _project_component() -> Optional[Component]:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    name = project.get("name")
    version = project.get("version")
    license_info = project.get("license") or {}
    license_text = None
    if isinstance(license_info, dict):
        license_text = license_info.get("text") or license_info.get("file")
    if not name or not version:
        return None
    return Component(name=name, version=version, license=license_text)


def generate_sbom() -> dict[str, object]:
    components = [component.to_dict() for component in _discover_components()]
    components.sort(key=lambda item: item["name"])
    project_component = _project_component()
    if project_component is not None:
        components.insert(0, project_component.to_dict())
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
