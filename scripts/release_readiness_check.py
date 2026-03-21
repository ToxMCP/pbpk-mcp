#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
CONTRACT_VERSION = "pbpk-mcp.v1"
PUBLISHED_CONTRACT_MANIFEST = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
CISPLATIN_MODEL = "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R"
PREGNANCY_PKML = "/app/var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml"
PKSIM5_PROJECT = "/app/var/demos/cimetidine/Cimetidine-Model.pksim5"
REQUIRED_TOOLS = {
    "discover_models",
    "ingest_external_pbpk_bundle",
    "validate_model_manifest",
    "load_simulation",
    "validate_simulation_request",
    "run_verification_checks",
    "run_simulation",
    "run_population_simulation",
    "get_job_status",
    "get_results",
    "get_population_results",
    "export_oecd_report",
}
REQUIRED_SCHEMA_IDS = {
    "assessmentContext.v1",
    "pbpkQualificationSummary.v1",
    "uncertaintySummary.v1",
    "uncertaintyHandoff.v1",
    "uncertaintyRegisterReference.v1",
    "internalExposureEstimate.v1",
    "pointOfDepartureReference.v1",
    "berInputBundle.v1",
}


def http_json(url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["content-type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {json.dumps(parsed)}") from exc


def call_tool(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 60) -> dict:
    response = http_json(
        f"{base_url}/mcp/call_tool",
        payload={"tool": tool, "arguments": arguments, **({"critical": True} if critical else {})},
        timeout=timeout,
    )
    return response["structuredContent"]


def call_tool_error(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 60) -> str:
    try:
        call_tool(base_url, tool, arguments, critical=critical, timeout=timeout)
    except RuntimeError as exc:
        return str(exc)
    raise RuntimeError(f"{tool} unexpectedly succeeded for arguments {arguments}")


def poll_job(base_url: str, job_id: str, timeout_seconds: int = 180) -> dict:
    deadline = time.time() + timeout_seconds
    last_status: dict | None = None
    while time.time() < deadline:
        payload = call_tool(base_url, "get_job_status", {"jobId": job_id}, timeout=30)
        last_status = payload
        if payload["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            return payload
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for job {job_id}: {json.dumps(last_status)}")


def run_bridge_tests() -> None:
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_capability_matrix.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_ngra_object_schemas.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_oecd_bridge.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_model_manifest.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_load_simulation_contract.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_external_pbpk_bundle.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_release_check(base_url: str, *, skip_unit_tests: bool = False) -> dict:
    if not skip_unit_tests:
        run_bridge_tests()

    summary: dict[str, object] = {}

    health = http_json(f"{base_url}/health", timeout=15)
    assert_true(health.get("status") == "ok", f"Health check failed: {health}")
    summary["health"] = health

    tool_catalog = http_json(f"{base_url}/mcp/list_tools", timeout=30)
    tool_names = {tool["name"] for tool in tool_catalog["tools"]}
    assert_true(
        REQUIRED_TOOLS.issubset(tool_names),
        f"Live tool catalog is missing required workflow tools: {sorted(REQUIRED_TOOLS - tool_names)}",
    )

    discovery = call_tool(base_url, "discover_models", {"search": "cisplatin", "limit": 20}, timeout=30)
    items = discovery["items"]
    cisplatin_matches = [item for item in items if "cisplatin" in item["filePath"].lower()]
    assert_true(bool(cisplatin_matches), "Cisplatin model not discoverable through discover_models")
    resource_models = http_json(f"{base_url}/mcp/resources/models?search=cisplatin&limit=20", timeout=30)
    resource_matches = [
        item for item in resource_models["items"] if "cisplatin" in item["filePath"].lower()
    ]
    assert_true(bool(resource_matches), "Cisplatin model not discoverable through /mcp/resources/models")
    assert_true(
        cisplatin_matches[0]["backend"] == resource_matches[0]["backend"],
        "discover_models and /mcp/resources/models disagree on the cisplatin backend",
    )
    assert_true(
        cisplatin_matches[0]["runtimeFormat"] == resource_matches[0]["runtimeFormat"],
        "discover_models and /mcp/resources/models disagree on the cisplatin runtime format",
    )
    summary["discovery"] = {
        "total": discovery["total"],
        "cisplatinMatches": len(cisplatin_matches),
        "firstBackend": cisplatin_matches[0]["backend"],
    }
    summary["toolCatalog"] = {
        "requiredTools": sorted(REQUIRED_TOOLS),
        "missingTools": sorted(REQUIRED_TOOLS - tool_names),
    }

    schema_catalog = http_json(f"{base_url}/mcp/resources/schemas?limit=50", timeout=30)
    schema_ids = {item["schemaId"] for item in schema_catalog["items"]}
    assert_true(
        REQUIRED_SCHEMA_IDS.issubset(schema_ids),
        f"Schema resources are missing published PBPK object schemas: {sorted(REQUIRED_SCHEMA_IDS - schema_ids)}",
    )
    assessment_schema = http_json(f"{base_url}/mcp/resources/schemas/assessmentContext.v1", timeout=30)
    assert_true(
        assessment_schema["schema"]["title"] == "assessmentContext.v1",
        "assessmentContext schema resource returned the wrong schema title",
    )
    assert_true(
        assessment_schema["example"]["objectType"] == "assessmentContext.v1",
        "assessmentContext schema resource returned the wrong example payload",
    )
    capability_resource = http_json(f"{base_url}/mcp/resources/capability-matrix", timeout=30)
    matrix = capability_resource["matrix"]
    matrix_entries = {entry["id"]: entry for entry in matrix["entries"]}
    published_contract_manifest = json.loads(PUBLISHED_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
    assert_true(
        matrix.get("contractVersion") == CONTRACT_VERSION,
        f"Capability matrix resource should advertise {CONTRACT_VERSION}: {matrix}",
    )
    assert_true(
        capability_resource.get("sha256")
        == (published_contract_manifest.get("capabilityMatrix") or {}).get("sha256"),
        "Capability matrix resource should expose the published capability-matrix SHA-256 from the contract manifest",
    )
    assert_true(
        matrix_entries["pksim5-project"]["policy"] == "conversion-only",
        "Capability matrix resource should preserve the conversion-only PK-Sim boundary",
    )
    contract_manifest_resource = http_json(f"{base_url}/mcp/resources/contract-manifest", timeout=30)
    manifest = contract_manifest_resource["manifest"]
    assert_true(
        manifest.get("contractVersion") == CONTRACT_VERSION,
        f"Contract manifest resource should advertise {CONTRACT_VERSION}: {manifest}",
    )
    assert_true(
        contract_manifest_resource.get("sha256") == file_sha256(PUBLISHED_CONTRACT_MANIFEST),
        "Contract manifest resource should expose the SHA-256 of the published contract manifest artifact",
    )
    assert_true(
        int((manifest.get("artifactCounts") or {}).get("schemas") or 0) == len(REQUIRED_SCHEMA_IDS),
        "Contract manifest should inventory the full published PBPK-side schema family",
    )
    manifest_schema_ids = {entry["schemaId"] for entry in manifest.get("schemas") or []}
    assert_true(
        REQUIRED_SCHEMA_IDS.issubset(manifest_schema_ids),
        f"Contract manifest is missing published schema ids: {sorted(REQUIRED_SCHEMA_IDS - manifest_schema_ids)}",
    )
    assessment_manifest_entry = next(
        entry for entry in manifest.get("schemas") or [] if entry["schemaId"] == "assessmentContext.v1"
    )
    assert_true(
        assessment_schema.get("sha256") == assessment_manifest_entry.get("sha256"),
        "Assessment schema resource should expose the published schema SHA-256 from the contract manifest",
    )
    assert_true(
        assessment_schema.get("exampleSha256") == assessment_manifest_entry.get("exampleSha256"),
        "Assessment schema resource should expose the published example SHA-256 from the contract manifest",
    )
    assert_true(
        "schemas/extraction-record.json" in (manifest.get("legacyArtifactsExcluded") or []),
        "Contract manifest should explicitly exclude the legacy extraction-record schema from the PBPK-side object family",
    )
    assert_true(
        (manifest.get("contractManifest") or {}).get("classification") == "normative",
        "Contract manifest should classify its own JSON artifact as normative",
    )
    assert_true(
        (manifest.get("capabilityMatrix") or {}).get("classification") == "normative",
        "Contract manifest should classify the capability matrix as normative",
    )
    assert_true(
        all(entry.get("classification") == "normative" for entry in manifest.get("schemas") or []),
        "Contract manifest should classify published schema entries as normative",
    )
    supporting_artifacts = manifest.get("supportingArtifacts") or []
    assert_true(
        all(entry.get("classification") == "supporting" for entry in supporting_artifacts),
        "Contract manifest should classify supporting artifacts explicitly",
    )
    assert_true(
        any(entry.get("relativePath") == "schemas/README.md" for entry in supporting_artifacts),
        "Contract manifest should inventory supporting schema documentation",
    )
    legacy_policy = manifest.get("legacyArtifactPolicy") or []
    assert_true(
        any(
            entry.get("relativePath") == "schemas/extraction-record.json"
            and entry.get("classification") == "legacy-excluded"
            for entry in legacy_policy
        ),
        "Contract manifest should publish the legacy-excluded extraction-record policy entry",
    )
    summary["resourceCatalog"] = {
        "schemaCount": schema_catalog["total"],
        "assessmentContextSchemaPublished": "assessmentContext.v1" in schema_ids,
        "capabilityMatrixEntries": capability_resource["entryCount"],
        "contractManifestSchemas": int((manifest.get("artifactCounts") or {}).get("schemas") or 0),
        "contractManifestSupportingArtifacts": int((manifest.get("artifactCounts") or {}).get("supporting") or 0),
    }

    full_catalog = call_tool(base_url, "discover_models", {"limit": 200}, timeout=30)
    catalog_formats = sorted({item["runtimeFormat"] for item in full_catalog["items"]})
    assert_true(
        set(catalog_formats).issubset({"pkml", "r"}),
        f"discover_models exposed unsupported runtime formats: {catalog_formats}",
    )

    ospsuite_catalog = call_tool(
        base_url,
        "discover_models",
        {"backend": "ospsuite", "limit": 50},
        timeout=30,
    )
    pkml_matches = [
        item for item in ospsuite_catalog["items"] if item["filePath"] == PREGNANCY_PKML
    ]
    assert_true(bool(pkml_matches), "Reference .pkml model not discoverable through ospsuite catalog view")
    assert_true(
        not bool(pkml_matches[0]["populationSimulation"]),
        f"OSPSuite .pkml entry should not advertise generic population support: {pkml_matches[0]}",
    )
    assert_true(
        bool(cisplatin_matches[0]["populationSimulation"]),
        f"Reference rxode2 model should advertise declared population support: {cisplatin_matches[0]}",
    )
    summary["capabilityMatrix"] = {
        "discoverableRuntimeFormats": catalog_formats,
        "conversionOnlyFormatsExcludedFromCatalog": True,
        "ospsuitePkmlPopulationSimulation": bool(pkml_matches[0]["populationSimulation"]),
        "rxode2ReferencePopulationSimulation": bool(cisplatin_matches[0]["populationSimulation"]),
    }

    external_bundle = call_tool(
        base_url,
        "ingest_external_pbpk_bundle",
        {
            "sourcePlatform": "GastroPlus",
            "sourceVersion": "10.1",
            "modelName": "Release readiness external import",
            "assessmentContext": {
                "contextOfUse": {"regulatoryUse": "research-only"},
                "domain": {"species": "human", "route": "oral"},
                "targetOutput": "Plasma|Parent|Concentration",
            },
            "internalExposure": {
                "targetOutput": "Plasma|Parent|Concentration",
                "species": "human",
                "route": "oral",
                "metrics": {
                    "cmax": {"value": 2.5, "unit": "uM"},
                    "auc0Tlast": {"value": 7.1, "unit": "uM*h"},
                },
            },
            "qualification": {
                "evidenceLevel": "L2",
                "verificationStatus": "checked",
                "platformClass": "commercial",
            },
            "uncertaintyRegister": {
                "ref": "unc-reg-readiness-001",
                "source": "assessment-workbench",
                "scope": "tier-1-systemic",
            },
            "pod": {
                "ref": "pod-readiness-001",
                "metric": "cmax",
                "unit": "uM",
                "source": "httr-benchmark",
            },
            "comparisonMetric": "cmax",
        },
        timeout=30,
    )
    assert_true(
        external_bundle["ngraObjects"]["berInputBundle"]["status"] == "ready-for-external-ber-calculation",
        "External PBPK ingestion should produce a BER-ready bundle when PoD metadata and exposure metrics are present",
    )
    assert_true(
        external_bundle["ngraObjects"]["berInputBundle"]["decisionOwner"] == "external-orchestrator",
        "External PBPK ingestion should preserve the boundary that BER calculation is owned by an external orchestrator",
    )
    assert_true(
        external_bundle["ngraObjects"]["pointOfDepartureReference"]["status"] == "attached-external-reference",
        "External PBPK ingestion should normalize the external PoD reference into a typed handoff object",
    )
    assert_true(
        external_bundle["ngraObjects"]["uncertaintyHandoff"]["decisionOwner"] == "external-orchestrator",
        "External PBPK ingestion should keep cross-domain uncertainty synthesis outside PBPK MCP",
    )
    assert_true(
        external_bundle["ngraObjects"]["uncertaintyRegisterReference"]["status"] == "attached-external-reference",
        "External PBPK ingestion should normalize an external uncertainty-register reference when one is supplied",
    )
    summary["externalImport"] = {
        "sourcePlatform": external_bundle["externalRun"]["sourcePlatform"],
        "berBundleStatus": external_bundle["ngraObjects"]["berInputBundle"]["status"],
        "decisionOwner": external_bundle["ngraObjects"]["berInputBundle"]["decisionOwner"],
        "podReferenceStatus": external_bundle["ngraObjects"]["pointOfDepartureReference"]["status"],
        "uncertaintyHandoffStatus": external_bundle["ngraObjects"]["uncertaintyHandoff"]["status"],
        "uncertaintyRegisterStatus": external_bundle["ngraObjects"]["uncertaintyRegisterReference"]["status"],
    }

    pksim5_error = call_tool_error(
        base_url,
        "load_simulation",
        {"filePath": PKSIM5_PROJECT, "simulationId": f"reject-pksim5-{uuid4().hex[:8]}"},
        critical=True,
        timeout=60,
    )
    assert_true(
        "Direct .pksim5 loading is not supported" in pksim5_error,
        f".pksim5 rejection message was not explicit enough: {pksim5_error}",
    )
    assert_true(
        "export the PK-Sim project to .pkml first" in pksim5_error,
        f".pksim5 rejection message did not include conversion guidance: {pksim5_error}",
    )

    manifest_check = call_tool(
        base_url,
        "validate_model_manifest",
        {"filePath": CISPLATIN_MODEL},
        timeout=60,
    )
    assert_true(
        manifest_check["manifest"]["qualificationState"]["state"] == "research-use",
        f"Unexpected cisplatin manifest qualification state: {manifest_check}",
    )
    assert_true(
        manifest_check["manifest"]["manifestStatus"] in {"valid", "partial"},
        f"Cisplatin manifest should be statically inspectable: {manifest_check}",
    )

    cis_id = f"release-cis-{uuid4().hex[:8]}"
    cis_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": CISPLATIN_MODEL, "simulationId": cis_id},
        critical=True,
        timeout=120,
    )
    assert_true(cis_load["backend"] == "rxode2", f"Unexpected cisplatin backend: {cis_load}")

    cis_validation = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": cis_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}},
        timeout=60,
    )
    assert_true(cis_validation["validation"]["ok"] is True, "Cisplatin validation did not pass in-domain")
    assert_true(
        cis_validation["ngraObjects"]["assessmentContext"]["objectType"] == "assessmentContext.v1",
        "validate_simulation_request should expose an assessmentContext NGRA object",
    )
    assert_true(
        cis_validation["ngraObjects"]["pbpkQualificationSummary"]["state"] == "research-use",
        "validate_simulation_request should expose the derived PBPK qualification summary",
    )
    assert_true(
        cis_validation["ngraObjects"]["internalExposureEstimate"]["status"] == "not-available",
        "validate_simulation_request should not fabricate an internal exposure estimate before a deterministic run exists",
    )

    cis_verification = call_tool(
        base_url,
        "run_verification_checks",
        {
            "simulationId": cis_id,
            "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
            "includePopulationSmoke": True,
            "populationCohort": {"size": 10, "seed": 42},
            "populationOutputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
        },
        timeout=180,
    )
    assert_true(
        cis_verification["verification"]["status"] == "passed",
        f"Cisplatin verification checks did not pass: {cis_verification}",
    )
    assert_true(
        any(check["id"] == "deterministic-smoke" for check in cis_verification["verification"]["checks"]),
        "Verification output is missing the deterministic smoke check",
    )
    assert_true(
        any(check["id"] == "population-smoke" for check in cis_verification["verification"]["checks"]),
        "Verification output is missing the population smoke check",
    )
    assert_true(
        any(
            check["id"] == "deterministic-integrity" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the deterministic integrity check",
    )
    assert_true(
        any(
            check["id"] == "deterministic-reproducibility" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the deterministic reproducibility check",
    )
    assert_true(
        any(
            check["id"] == "parameter-unit-consistency" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the parameter-unit-consistency check",
    )
    assert_true(
        any(
            check["id"] == "systemic-flow-consistency" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the systemic-flow-consistency check",
    )
    assert_true(
        any(
            check["id"] == "renal-volume-consistency" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the renal-volume-consistency check",
    )
    assert_true(
        any(
            check["id"] == "mass-balance" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the mass-balance check",
    )
    assert_true(
        any(
            check["id"] == "solver-stability" and check["status"] == "passed"
            for check in cis_verification["verification"]["checks"]
        ),
        "Verification output is missing the solver-stability check",
    )

    cis_report = call_tool(
        base_url,
        "export_oecd_report",
        {"simulationId": cis_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}, "parameterLimit": 5},
        timeout=120,
    )
    cis_report_payload = cis_report["report"]
    assert_true(cis_report["tool"] == "export_oecd_report", "export_oecd_report tool response missing")
    assert_true(cis_report_payload["reportVersion"] == "pbpk-oecd-report.v1", "Unexpected OECD report version")
    assert_true(
        cis_report_payload["oecdCoverage"]["coverageVersion"] == "pbpk-oecd-coverage.v1",
        "The exported OECD report should carry the additive OECD coverage map",
    )
    assert_true(
        cis_report_payload["oecdCoverage"]["affectsChecklistScore"] is False,
        "OECD coverage mapping must remain descriptive and must not affect the checklist score",
    )
    assert_true(
        cis_report["ngraObjects"]["assessmentContext"]["objectType"] == "assessmentContext.v1",
        "export_oecd_report should expose top-level NGRA objects for downstream workflows",
    )
    assert_true(
        "ngraObjects" in cis_report_payload,
        "The exported OECD report should remain self-contained and carry its NGRA object block",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["internalExposureEstimate"]["status"] == "available",
        "The exported OECD report should derive internal exposure from the latest deterministic results handle",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["berInputBundle"]["status"] == "incomplete",
        "The PBPK-side BER bundle should remain incomplete until an external point-of-departure reference is attached",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["uncertaintyHandoff"]["status"] == "ready-for-cross-domain-uncertainty-synthesis",
        "The exported OECD report should expose a ready PBPK-side uncertainty handoff object",
    )
    assert_true(
        cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"] == "partial",
        "Cisplatin performance checklist should remain partial until real fit evidence is attached",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["returnedRows"] >= 1,
        "Cisplatin report should include exported performance evidence rows",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["strongestEvidenceClass"] == "runtime-smoke",
        "Cisplatin report should classify bundled performance evidence as runtime smoke only",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["qualificationBoundary"] == "runtime-or-internal-evidence-only",
        "Cisplatin report should keep a runtime/internal-only qualification boundary until predictive datasets are attached",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["limitedToRuntimeOrInternalEvidence"] is True,
        "Cisplatin report should explicitly mark its current performance evidence as runtime/internal only",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsObservedVsPredictedEvidence"] is False,
        "Cisplatin report must not claim observed-versus-predicted evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsPredictiveDatasetEvidence"] is False,
        "Cisplatin report must not claim predictive-dataset evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsExternalQualificationEvidence"] is False,
        "Cisplatin report must not claim external qualification evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["parameterTable"]["coverage"]["rowCount"] == cis_report_payload["parameterTable"]["matchedRows"],
        "Parameter-table coverage should describe the matched parameter table rows",
    )
    assert_true(
        "rowsWithExperimentalConditions" in cis_report_payload["parameterTable"]["coverage"],
        "Parameter-table coverage should expose study-condition coverage counts",
    )
    uncertainty_row_ids = {entry["id"] for entry in cis_report_payload["uncertaintyEvidence"]["rows"]}
    assert_true(
        "bounded-variability-propagation-summary" in uncertainty_row_ids,
        f"Cisplatin report uncertainty evidence is missing the variability propagation summary row: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        any(row_id.startswith("bounded-variability-propagation-") and row_id != "bounded-variability-propagation-summary" for row_id in uncertainty_row_ids),
        f"Cisplatin report uncertainty evidence is missing quantitative variability propagation rows: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        "local-sensitivity-screen-summary" in uncertainty_row_ids,
        f"Cisplatin report uncertainty evidence is missing the local sensitivity summary row: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        any(row_id.startswith("local-sensitivity-") and row_id != "local-sensitivity-screen-summary" for row_id in uncertainty_row_ids),
        f"Cisplatin report uncertainty evidence is missing quantitative local sensitivity rows: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        cis_report_payload["executableVerification"]["included"] is True,
        "Cisplatin report should include the stored executable verification snapshot after run_verification_checks",
    )
    assert_true(
        cis_report_payload["executableVerification"]["status"] == "passed",
        f"Cisplatin report carried an unexpected executable verification status: {cis_report_payload['executableVerification']}",
    )
    report_check_ids = {entry["id"] for entry in cis_report_payload["executableVerification"]["checks"]}
    assert_true(
        "mass-balance" in report_check_ids,
        f"Cisplatin report executable verification is missing the mass-balance check: {sorted(report_check_ids)}",
    )
    assert_true(
        "parameter-unit-consistency" in report_check_ids,
        f"Cisplatin report executable verification is missing the parameter-unit-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "systemic-flow-consistency" in report_check_ids,
        f"Cisplatin report executable verification is missing the systemic-flow-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "renal-volume-consistency" in report_check_ids,
        f"Cisplatin report executable verification is missing the renal-volume-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "solver-stability" in report_check_ids,
        f"Cisplatin report executable verification is missing the solver-stability check: {sorted(report_check_ids)}",
    )

    run_id = f"{cis_id}-smoke"
    cis_submit = call_tool(
        base_url,
        "run_simulation",
        {"simulationId": cis_id, "runId": run_id},
        critical=True,
        timeout=60,
    )
    cis_job = poll_job(base_url, cis_submit["jobId"])
    assert_true(cis_job["status"] == "succeeded", f"Cisplatin simulation failed: {cis_job}")
    cis_results = call_tool(base_url, "get_results", {"resultsId": cis_job["resultId"]}, timeout=60)
    assert_true(len(cis_results["series"]) > 0, "Cisplatin deterministic result returned no series")

    population_tool_schema = next(
        tool for tool in tool_catalog["tools"] if tool["name"] == "run_population_simulation"
    )
    required_population_fields = set(population_tool_schema["inputSchema"].get("required") or [])
    assert_true(
        "modelPath" not in required_population_fields,
        f"run_population_simulation should not require modelPath in the converged contract: {required_population_fields}",
    )

    cis_population = call_tool(
        base_url,
        "run_population_simulation",
        {
            "simulationId": cis_id,
            "cohort": {"size": 10, "seed": 42},
            "outputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
        },
        critical=True,
        timeout=60,
    )
    cis_population_job = poll_job(base_url, cis_population["jobId"], timeout_seconds=240)
    assert_true(
        cis_population_job["status"] == "succeeded",
        f"Cisplatin population simulation failed: {cis_population_job}",
    )
    cis_population_results = call_tool(
        base_url,
        "get_population_results",
        {"resultsId": cis_population_job["resultId"]},
        timeout=60,
    )
    assert_true(
        len(cis_population_results.get("aggregates") or {}) > 0,
        "Cisplatin population result returned no aggregates",
    )

    pkml_id = f"release-pkml-{uuid4().hex[:8]}"
    pkml_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": PREGNANCY_PKML, "simulationId": pkml_id},
        critical=True,
        timeout=120,
    )
    assert_true(pkml_load["backend"] == "ospsuite", f"Unexpected PKML backend: {pkml_load}")

    pkml_report = call_tool(
        base_url,
        "export_oecd_report",
        {"simulationId": pkml_id, "request": {"contextOfUse": "research-only"}, "parameterLimit": 3},
        timeout=120,
    )
    pkml_report_payload = pkml_report["report"]
    assert_true(pkml_report_payload["profile"]["profileSource"]["type"] == "sidecar", "OSPSuite sidecar provenance was not preserved")
    assert_true(pkml_report_payload["parameterTable"]["returnedRows"] > 0, "OSPSuite OECD report should include runtime parameter rows")

    summary["cisplatin"] = {
        "simulationId": cis_id,
        "manifestState": manifest_check["manifest"]["qualificationState"]["state"],
        "validationDecision": cis_validation["validation"]["assessment"]["decision"],
        "verificationStatus": cis_verification["verification"]["status"],
        "executableVerificationStatus": cis_report_payload["executableVerification"]["status"],
        "reportChecklistScore": cis_report_payload["oecdChecklistScore"],
        "performanceChecklistStatus": cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"],
        "performanceEvidenceRows": cis_report_payload["performanceEvidence"]["returnedRows"],
        "performanceEvidenceBoundary": cis_report_payload["performanceEvidence"]["qualificationBoundary"],
        "uncertaintyHandoffStatus": cis_report_payload["ngraObjects"]["uncertaintyHandoff"]["status"],
        "resultSeries": len(cis_results["series"]),
        "populationAggregates": sorted((cis_population_results.get("aggregates") or {}).keys()),
    }
    summary["ospsuite"] = {
        "simulationId": pkml_id,
        "reportDecision": pkml_report_payload["validation"]["assessment"]["decision"],
        "profileSource": pkml_report_payload["profile"]["profileSource"]["type"],
        "parameterRows": pkml_report_payload["parameterTable"]["returnedRows"],
    }

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run release-readiness checks against the local PBPK MCP stack.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="PBPK MCP base URL.")
    parser.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="Skip the local OECD bridge unit tests and only run live stack checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_release_check(args.base_url, skip_unit_tests=args.skip_unit_tests)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
