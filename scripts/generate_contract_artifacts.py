#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import tomllib
from collections import Counter
from pathlib import Path

from contract_stage_utils import COPY_IGNORE_GLOBS


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_MATRIX_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "capability_matrix.json"
CONTRACT_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
RELEASE_BUNDLE_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "release_bundle_manifest.json"
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
        "benchmarks/regulatory_goldset/README.md",
        "regulatory benchmark corpus guide",
    ),
    (
        "benchmarks/regulatory_goldset/sources.lock.json",
        "regulatory gold-set source lock",
    ),
    (
        "benchmarks/regulatory_goldset/fetched.lock.json",
        "regulatory gold-set fetch lock",
    ),
    (
        "benchmarks/regulatory_goldset/regulatory_goldset_scorecard.json",
        "regulatory gold-set scorecard",
    ),
    (
        "benchmarks/regulatory_goldset/regulatory_goldset_summary.md",
        "regulatory gold-set benchmark summary",
    ),
    (
        "benchmarks/regulatory_goldset/regulatory_goldset_audit_manifest.json",
        "regulatory gold-set audit manifest",
    ),
    (
        "docs/architecture/capability_matrix.md",
        "human-readable capability guide",
    ),
    (
        "docs/architecture/mcp_payload_conventions.md",
        "payload contract reference",
    ),
    (
        "docs/architecture/exposure_led_ngra_role.md",
        "exposure-led NGRA boundary guide",
    ),
    (
        "docs/architecture/toxmcp_suite_index.md",
        "cross-service suite routing guide",
    ),
    (
        "docs/architecture/release_bundle_manifest.json",
        "whole release bundle hash inventory",
    ),
    (
        "docs/hardening_migration_notes.md",
        "hardening migration notes",
    ),
    (
        "docs/pbpk_model_onboarding_checklist.md",
        "PBPK model onboarding checklist",
    ),
    (
        "docs/github_publication_checklist.md",
        "publication checklist",
    ),
    (
        "docs/pbk_reviewer_signoff_checklist.md",
        "PBK reviewer sign-off checklist",
    ),
    (
        "docs/post_release_audit_plan.md",
        "post-release audit plan",
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
        "scripts/release_readiness_check.py",
        "live release readiness gate",
    ),
    (
        "scripts/wait_for_runtime_ready.py",
        "runtime readiness probe",
    ),
    (
        "scripts/workspace_model_smoke.py",
        "workspace live smoke script",
    ),
    (
        "scripts/generate_contract_artifacts.py",
        "contract artifact generator",
    ),
    (
        "scripts/generate_regulatory_goldset_audit.py",
        "regulatory gold-set audit generator",
    ),
    (
        "src/mcp_bridge/trust_surface.py",
        "thin-client trust-surface contract helper",
    ),
    (
        "src/mcp_bridge/benchmarking/regulatory_goldset.py",
        "regulatory gold-set benchmark helper",
    ),
    (
        "tests/test_release_readiness_script.py",
        "release readiness regression test",
    ),
    (
        "tests/test_regulatory_goldset_analysis.py",
        "regulatory gold-set analysis regression test",
    ),
    (
        "tests/test_trust_surface.py",
        "trust-surface contract regression test",
    ),
    (
        "tests/test_runtime_security_live_stack.py",
        "live runtime security regression test",
    ),
    (
        "tests/test_model_discovery_live_stack.py",
        "live model discovery regression test",
    ),
    (
        "tests/test_oecd_live_stack.py",
        "live OECD workflow regression test",
    ),
)
RESOURCE_ENDPOINTS = {
    "capabilityMatrix": "/mcp/resources/capability-matrix",
    "contractManifest": "/mcp/resources/contract-manifest",
    "releaseBundleManifest": "/mcp/resources/release-bundle-manifest",
    "schemaCatalog": "/mcp/resources/schemas",
}
MCP_RESOURCE_URIS = {
    "capabilityMatrix": "pbpk://capability-matrix",
    "contractManifest": "pbpk://contract-manifest",
    "releaseBundleManifest": "pbpk://release-bundle-manifest",
    "schemaCatalog": "pbpk://schemas/catalog",
    "schemaTemplate": "pbpk://schemas/{schemaId}",
    "models": "pbpk://models",
    "simulations": "pbpk://simulations",
    "parametersTemplate": "pbpk://parameters/{simulationId}",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _release_bundle_manifest_relative_path() -> str:
    return RELEASE_BUNDLE_MANIFEST_PATH.relative_to(WORKSPACE_ROOT).as_posix()


def _package_version() -> str:
    pyproject = tomllib.loads((WORKSPACE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(((pyproject.get("project") or {}).get("version")) or "unknown")


def _should_ignore_name(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in COPY_IGNORE_GLOBS)


def _release_bundle_group(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if not parts:
        return "root"
    first = parts[0]
    return {
        ".github": "governance",
        "docker": "container",
        "docs": "documentation",
        "schemas": "contract",
        "scripts": "operations",
        "src": "source",
        "tests": "verification",
        "ui": "ui",
    }.get(first, "root")


def _release_bundle_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    excluded_paths = {
        _release_bundle_manifest_relative_path(),
        CONTRACT_MANIFEST_PATH.relative_to(WORKSPACE_ROOT).as_posix(),
        PACKAGED_MODULE_PATH.relative_to(WORKSPACE_ROOT).as_posix(),
    }
    for root, dirnames, filenames in os.walk(WORKSPACE_ROOT):
        dirnames[:] = sorted(name for name in dirnames if not _should_ignore_name(name))
        for filename in sorted(filenames):
            if _should_ignore_name(filename):
                continue
            path = Path(root) / filename
            relative_path = path.relative_to(WORKSPACE_ROOT).as_posix()
            if relative_path in excluded_paths:
                continue
            entries.append(
                {
                    "relativePath": relative_path,
                    "sha256": _sha256(path),
                    "sizeBytes": path.stat().st_size,
                    "group": _release_bundle_group(relative_path),
                }
            )
    return entries


def _bundle_sha256(entries: list[dict[str, object]]) -> str:
    payload = "\n".join(
        f"{entry['relativePath']}:{entry['sha256']}:{entry['sizeBytes']}"
        for entry in entries
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_release_bundle_manifest(capability_matrix: dict) -> dict:
    entries = _release_bundle_entries()
    group_counts = Counter(str(entry["group"]) for entry in entries)
    total_bytes = sum(int(entry["sizeBytes"]) for entry in entries)
    return {
        "id": "pbpk-release-bundle-manifest.v1",
        "contractVersion": capability_matrix["contractVersion"],
        "packageVersion": _package_version(),
        "selectionPolicy": {
            "mode": "staged-source-tree-equivalent",
            "excludedPatterns": list(COPY_IGNORE_GLOBS),
            "acyclicIntegrityExclusions": [
                _release_bundle_manifest_relative_path(),
                CONTRACT_MANIFEST_PATH.relative_to(WORKSPACE_ROOT).as_posix(),
                PACKAGED_MODULE_PATH.relative_to(WORKSPACE_ROOT).as_posix(),
            ],
        },
        "bundleSha256": _bundle_sha256(entries),
        "fileCount": len(entries),
        "totalBytes": total_bytes,
        "groupCounts": dict(sorted(group_counts.items())),
        "files": entries,
    }


def _build_contract_manifest(
    capability_matrix: dict,
    schema_documents: dict[str, dict],
    schema_examples: dict[str, dict],
    *,
    supporting_sha_overrides: dict[str, str] | None = None,
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
            "sha256": (supporting_sha_overrides or {}).get(relative_path)
            or _sha256(WORKSPACE_ROOT / relative_path),
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
        "mcpResourceUris": MCP_RESOURCE_URIS,
        "schemas": entries,
        "supportingArtifacts": supporting_artifacts,
    }


def _build_packaged_module(
    capability_matrix: dict,
    contract_manifest: dict,
    release_bundle_manifest: dict,
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
        '_RELEASE_BUNDLE_MANIFEST_JSON = r"""',
        _render_json(release_bundle_manifest),
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
            "def release_bundle_manifest_document() -> dict[str, object]:",
            "    return json.loads(_RELEASE_BUNDLE_MANIFEST_JSON)",
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
        help="Fail if the checked-in release/contract manifests or packaged contract module are out of date.",
    )
    args = parser.parse_args()

    capability_matrix, schema_documents, schema_examples = _current_contract_inputs()
    release_bundle_manifest = _build_release_bundle_manifest(capability_matrix)
    release_bundle_manifest_text = _render_json(release_bundle_manifest) + "\n"
    release_bundle_manifest_sha256 = hashlib.sha256(
        release_bundle_manifest_text.encode("utf-8")
    ).hexdigest()
    contract_manifest = _build_contract_manifest(
        capability_matrix,
        schema_documents,
        schema_examples,
        supporting_sha_overrides={
            _release_bundle_manifest_relative_path(): release_bundle_manifest_sha256,
        },
    )
    manifest_text = _render_json(contract_manifest) + "\n"
    packaged_module_text = _build_packaged_module(
        capability_matrix,
        contract_manifest,
        release_bundle_manifest,
        schema_documents,
        schema_examples,
    )

    if args.check:
        ok = True
        ok = _check_file(RELEASE_BUNDLE_MANIFEST_PATH, release_bundle_manifest_text) and ok
        ok = _check_file(CONTRACT_MANIFEST_PATH, manifest_text) and ok
        ok = _check_file(PACKAGED_MODULE_PATH, packaged_module_text) and ok
        return 0 if ok else 1

    RELEASE_BUNDLE_MANIFEST_PATH.write_text(release_bundle_manifest_text, encoding="utf-8")
    CONTRACT_MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    PACKAGED_MODULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED_MODULE_PATH.write_text(packaged_module_text, encoding="utf-8")
    print(f"Wrote {RELEASE_BUNDLE_MANIFEST_PATH}")
    print(f"Wrote {CONTRACT_MANIFEST_PATH}")
    print(f"Wrote {PACKAGED_MODULE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
