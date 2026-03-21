#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_MATRIX_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "capability_matrix.json"
CONTRACT_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
SCHEMA_ROOT = WORKSPACE_ROOT / "schemas"
SCHEMA_EXAMPLES_ROOT = SCHEMA_ROOT / "examples"
PACKAGED_MODULE_PATH = WORKSPACE_ROOT / "src" / "mcp_bridge" / "contract" / "artifacts.py"
LEGACY_EXCLUDED = ["schemas/extraction-record.json"]
ARTIFACT_CLASSES = {
    "legacy-excluded": {
        "description": "Historical or non-PBPK-side artifacts that are intentionally outside pbpk-mcp.v1."
    },
    "normative": {
        "description": "Machine-readable artifacts that define the published pbpk-mcp.v1 contract."
    },
    "supporting": {
        "description": "Human-facing or release-facing artifacts that support the contract without defining it."
    },
}
SUPPORTING_ARTIFACTS = (
    (
        "docs/architecture/capability_matrix.md",
        "human-readable capability guide",
    ),
    (
        "docs/architecture/mcp_payload_conventions.md",
        "payload contract reference",
    ),
    (
        "docs/github_publication_checklist.md",
        "publication checklist",
    ),
    (
        "schemas/README.md",
        "schema usage guide",
    ),
    (
        "scripts/check_distribution_artifacts.py",
        "distribution artifact validation script",
    ),
    (
        "scripts/check_release_metadata.py",
        "release metadata consistency check",
    ),
    (
        "scripts/check_installed_package_contract.py",
        "installed package contract validation script",
    ),
    (
        "scripts/check_runtime_contract_env.py",
        "contract dependency preflight script",
    ),
    (
        "scripts/generate_contract_artifacts.py",
        "contract artifact generator",
    ),
)
RESOURCE_ENDPOINTS = {
    "capabilityMatrix": "/mcp/resources/capability-matrix",
    "contractManifest": "/mcp/resources/contract-manifest",
    "schemaCatalog": "/mcp/resources/schemas",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _build_contract_manifest(
    capability_matrix: dict,
    schema_documents: dict[str, dict],
    schema_examples: dict[str, dict],
) -> dict:
    entries: list[dict[str, object]] = []
    for schema_id in sorted(schema_documents):
        schema_filename = f"{schema_id}.json"
        example_filename = f"{schema_id}.example.json"
        schema_path = SCHEMA_ROOT / schema_filename
        example_path = SCHEMA_EXAMPLES_ROOT / example_filename
        entry = {
            "classification": "normative",
            "schemaId": schema_id,
            "relativePath": f"schemas/{schema_filename}",
            "sha256": _sha256(schema_path),
            "exampleRelativePath": f"schemas/examples/{example_filename}",
            "exampleSha256": _sha256(example_path),
        }
        entries.append(entry)

    supporting_artifacts = [
        {
            "classification": "supporting",
            "relativePath": relative_path,
            "role": role,
            "sha256": _sha256(WORKSPACE_ROOT / relative_path),
        }
        for relative_path, role in SUPPORTING_ARTIFACTS
    ]

    return {
        "id": "pbpk-contract-manifest.v1",
        "contractVersion": capability_matrix["contractVersion"],
        "artifactClasses": ARTIFACT_CLASSES,
        "artifactCounts": {
            "examples": len(schema_examples),
            "schemas": len(schema_documents),
            "supporting": len(supporting_artifacts),
        },
        "contractManifest": {
            "classification": "normative",
            "relativePath": "docs/architecture/contract_manifest.json",
        },
        "capabilityMatrix": {
            "classification": "normative",
            "relativePath": "docs/architecture/capability_matrix.json",
            "sha256": _sha256(CAPABILITY_MATRIX_PATH),
        },
        "legacyArtifactsExcluded": LEGACY_EXCLUDED,
        "legacyArtifactPolicy": [
            {
                "classification": "legacy-excluded",
                "reason": "Legacy literature extraction schema retained outside the PBPK-side pbpk-mcp.v1 object family.",
                "relativePath": relative_path,
            }
            for relative_path in LEGACY_EXCLUDED
        ],
        "resourceEndpoints": RESOURCE_ENDPOINTS,
        "schemas": entries,
        "supportingArtifacts": supporting_artifacts,
    }


def _build_packaged_module(
    capability_matrix: dict,
    contract_manifest: dict,
    schema_documents: dict[str, dict],
    schema_examples: dict[str, dict],
) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "import json",
        "",
        '_CAPABILITY_MATRIX_JSON = r"""',
        _render_json(capability_matrix),
        '"""',
        "",
        '_CONTRACT_MANIFEST_JSON = r"""',
        _render_json(contract_manifest),
        '"""',
        "",
        "_SCHEMA_JSON = {",
    ]
    for schema_id in sorted(schema_documents):
        lines.extend(
            [
                f"    {schema_id!r}: r\"\"\"",
                _render_json(schema_documents[schema_id]),
                '""",',
            ]
        )
    lines.extend(["}", "", "_SCHEMA_EXAMPLE_JSON = {"])
    for schema_id in sorted(schema_examples):
        lines.extend(
            [
                f"    {schema_id!r}: r\"\"\"",
                _render_json(schema_examples[schema_id]),
                '""",',
            ]
        )
    lines.extend(
        [
            "}",
            "",
            "def capability_matrix_document() -> dict[str, object]:",
            "    return json.loads(_CAPABILITY_MATRIX_JSON)",
            "",
            "def contract_manifest_document() -> dict[str, object]:",
            "    return json.loads(_CONTRACT_MANIFEST_JSON)",
            "",
            "def schema_documents() -> dict[str, dict]:",
            "    return {key: json.loads(value) for key, value in _SCHEMA_JSON.items()}",
            "",
            "def schema_examples() -> dict[str, dict]:",
            "    return {key: json.loads(value) for key, value in _SCHEMA_EXAMPLE_JSON.items()}",
            "",
        ]
    )
    return "\n".join(lines)


def _current_contract_inputs() -> tuple[dict, dict[str, dict], dict[str, dict]]:
    capability_matrix = _load_json(CAPABILITY_MATRIX_PATH)
    schema_documents = {
        path.stem: _load_json(path) for path in sorted(SCHEMA_ROOT.glob("*.v*.json"))
    }
    schema_examples = {
        path.name.replace(".example.json", ""): _load_json(path)
        for path in sorted(SCHEMA_EXAMPLES_ROOT.glob("*.json"))
    }
    return capability_matrix, schema_documents, schema_examples


def _check_file(path: Path, expected: str) -> bool:
    if not path.exists():
        print(f"Missing generated file: {path}", file=sys.stderr)
        return False
    current = path.read_text(encoding="utf-8")
    if current != expected:
        print(f"Generated file is out of date: {path}", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in contract manifest or packaged contract module are out of date.",
    )
    args = parser.parse_args()

    capability_matrix, schema_documents, schema_examples = _current_contract_inputs()
    contract_manifest = _build_contract_manifest(
        capability_matrix,
        schema_documents,
        schema_examples,
    )
    manifest_text = _render_json(contract_manifest) + "\n"
    packaged_module_text = _build_packaged_module(
        capability_matrix,
        contract_manifest,
        schema_documents,
        schema_examples,
    )

    if args.check:
        ok = True
        ok = _check_file(CONTRACT_MANIFEST_PATH, manifest_text) and ok
        ok = _check_file(PACKAGED_MODULE_PATH, packaged_module_text) and ok
        return 0 if ok else 1

    CONTRACT_MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    PACKAGED_MODULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED_MODULE_PATH.write_text(packaged_module_text, encoding="utf-8")
    print(f"Wrote {CONTRACT_MANIFEST_PATH}")
    print(f"Wrote {PACKAGED_MODULE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
