from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import unittest
from pathlib import Path
from uuid import uuid4


API_BASE_URL = "http://127.0.0.1:8000"
API_CONTAINER = "pbpk_mcp-api-1"
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
RELEASE_BUNDLE_MANIFEST_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "release_bundle_manifest.json"
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.contract import published_schema_ids, release_probe_required_tools  # noqa: E402
from mcp_bridge.security.simple_jwt import jwt  # noqa: E402

DEV_AUTH_SECRET = "pbpk-local-dev-secret-32bytes-long"
LIVE_HTTP_TIMEOUT_SECONDS = 60
LIVE_SUBPROCESS_TIMEOUT_SECONDS = 420


def _auth_headers() -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": "model-discovery-live-stack",
            "roles": ["operator"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        DEV_AUTH_SECRET,
        algorithm="HS256",
    )
    return {"authorization": f"Bearer {token}"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api_json(path: str, payload: dict | None = None, *, timeout: int = LIVE_HTTP_TIMEOUT_SECONDS):
    url = f"{API_BASE_URL}{path}"
    data = None
    headers = dict(_auth_headers())
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def call_tool(payload: dict):
    return api_json("/mcp/call_tool", payload)


@unittest.skipUnless(shutil.which("docker"), "docker is required for live-stack model discovery tests")
class ModelDiscoveryLiveStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        probe = subprocess.run(
            ["docker", "exec", API_CONTAINER, "true"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(f"{API_CONTAINER} is not available")
        cls.contract_manifest = _load_json(CONTRACT_MANIFEST_PATH)

    def test_resource_endpoint_discovers_reference_model(self) -> None:
        payload = api_json("/mcp/resources/models?search=reference_compound&limit=20")
        self.assertGreaterEqual(payload["total"], 1)

        matches = [
            item for item in payload["items"] if "reference_compound" in item["filePath"].lower()
        ]
        self.assertTrue(matches, "reference_compound model was not returned by /mcp/resources/models")

        item = matches[0]
        self.assertEqual(item["backend"], "rxode2")
        self.assertTrue(item["filePath"].endswith("reference_compound_population_rxode2_model.R"))
        self.assertEqual(item["runtimeFormat"], "r")
        self.assertIn(item["discoveryState"], {"discovered", "loaded"})
        self.assertEqual(item["manifestStatus"], "valid")
        self.assertEqual(item["qualificationState"]["state"], "research-use")
        self.assertTrue(item["curationSummary"]["ngraDeclarationsExplicit"])
        self.assertEqual(item["curationSummary"]["missingSections"], [])
        self.assertIn("complete static curation", item["curationSummary"]["reviewLabel"].lower())
        self.assertIn("misreadRiskSummary", item["curationSummary"])
        self.assertTrue(item["curationSummary"]["misreadRiskSummary"]["requiredReading"])
        self.assertIn(
            "static validation",
            item["curationSummary"]["misreadRiskSummary"]["sectionTitle"].lower(),
        )
        self.assertIn("renderingGuardrails", item["curationSummary"])
        self.assertFalse(item["curationSummary"]["renderingGuardrails"]["allowBareReviewLabel"])
        self.assertTrue(item["curationSummary"]["renderingGuardrails"]["requiresInlineMisreadGuidance"])
        self.assertEqual(
            item["curationSummary"]["renderingGuardrails"]["actionIfRequiredFieldsMissing"],
            "refuse-rendering",
        )
        self.assertIn("summaryTransportRisk", item["curationSummary"])
        self.assertEqual(item["curationSummary"]["summaryTransportRisk"]["riskLevel"], "high")
        self.assertTrue(item["curationSummary"]["summaryTransportRisk"]["detachedSummaryUnsafe"])
        self.assertIn("regulatoryBenchmarkReadiness", item["curationSummary"])
        benchmark_readiness = item["curationSummary"]["regulatoryBenchmarkReadiness"]
        self.assertTrue(benchmark_readiness["advisoryOnly"])
        self.assertEqual(
            benchmark_readiness["modelResemblance"],
            "research-example",
        )
        self.assertTrue(benchmark_readiness["benchmarkBarSource"]["sourceManifestSha256"])
        self.assertTrue(benchmark_readiness["benchmarkBarSource"]["fetchedLockSha256"])
        self.assertIn(
            benchmark_readiness["benchmarkBarSource"]["sourceResolution"],
            {"direct-lock-files", "audit-manifest-fallback", "packaged-contract-fallback"},
        )
        self.assertTrue(benchmark_readiness["recommendedNextArtifacts"])
        self.assertIn("cautionSummary", item["curationSummary"])
        self.assertEqual(item["curationSummary"]["cautionSummary"]["highestSeverity"], "high")
        self.assertIn(
            "detached-summary-overread",
            {entry["code"] for entry in item["curationSummary"]["cautionSummary"]["cautions"]},
        )
        self.assertIn("exportBlockPolicy", item["curationSummary"])
        self.assertIn(
            "detached-summary-blocked",
            {entry["code"] for entry in item["curationSummary"]["exportBlockPolicy"]["blockReasons"]},
        )

    def test_schema_resource_catalog_lists_published_objects(self) -> None:
        payload = api_json("/mcp/resources/schemas?limit=50")
        expected_schema_ids = set(published_schema_ids())
        self.assertGreaterEqual(payload["total"], len(expected_schema_ids))

        schema_ids = {item["schemaId"] for item in payload["items"]}
        self.assertTrue(expected_schema_ids.issubset(schema_ids))
        assessment_item = next(item for item in payload["items"] if item["schemaId"] == "assessmentContext.v1")
        manifest_entry = next(
            entry for entry in self.contract_manifest["schemas"] if entry["schemaId"] == "assessmentContext.v1"
        )
        self.assertEqual(assessment_item["relativePath"], "schemas/assessmentContext.v1.json")
        self.assertEqual(assessment_item["sha256"], manifest_entry["sha256"])
        self.assertEqual(
            assessment_item["exampleRelativePath"],
            "schemas/examples/assessmentContext.v1.example.json",
        )
        self.assertEqual(assessment_item["exampleSha256"], manifest_entry["exampleSha256"])

    def test_schema_resource_detail_returns_schema_and_example(self) -> None:
        payload = api_json("/mcp/resources/schemas/assessmentContext.v1")
        manifest_entry = next(
            entry for entry in self.contract_manifest["schemas"] if entry["schemaId"] == "assessmentContext.v1"
        )
        self.assertEqual(payload["schemaId"], "assessmentContext.v1")
        self.assertEqual(payload["schema"]["title"], "assessmentContext.v1")
        self.assertEqual(payload["example"]["objectType"], "assessmentContext.v1")
        self.assertEqual(payload["sha256"], manifest_entry["sha256"])
        self.assertEqual(payload["exampleSha256"], manifest_entry["exampleSha256"])

    def test_capability_matrix_resource_exposes_published_contract(self) -> None:
        payload = api_json("/mcp/resources/capability-matrix")
        self.assertEqual(payload["contractVersion"], "pbpk-mcp.v1")
        self.assertEqual(payload["sha256"], self.contract_manifest["capabilityMatrix"]["sha256"])
        self.assertEqual(payload["relativePath"], "docs/architecture/capability_matrix.json")
        self.assertGreaterEqual(payload["entryCount"], 5)
        entries = payload["matrix"]["entries"]
        conversion_only = next(entry for entry in entries if entry["id"] == "pksim5-project")
        self.assertEqual(conversion_only["policy"], "conversion-only")
        self.assertEqual(conversion_only["catalogDiscovery"], "no")

    def test_contract_manifest_resource_exposes_artifact_inventory(self) -> None:
        payload = api_json("/mcp/resources/contract-manifest")
        self.assertEqual(payload["contractVersion"], "pbpk-mcp.v1")
        self.assertEqual(payload["sha256"], _sha256(CONTRACT_MANIFEST_PATH))
        self.assertEqual(payload["relativePath"], "docs/architecture/contract_manifest.json")
        self.assertEqual(payload["schemaCount"], 8)
        self.assertEqual(payload["manifest"]["artifactCounts"]["schemas"], 8)
        self.assertEqual(payload["manifest"]["contractManifest"]["classification"], "normative")
        self.assertEqual(payload["manifest"]["capabilityMatrix"]["classification"], "normative")
        self.assertTrue(all(entry["classification"] == "normative" for entry in payload["manifest"]["schemas"]))
        self.assertGreaterEqual(payload["manifest"]["artifactCounts"]["supporting"], 4)
        self.assertTrue(
            any(
                entry["relativePath"] == "schemas/README.md" and entry["classification"] == "supporting"
                for entry in payload["manifest"]["supportingArtifacts"]
            )
        )
        self.assertTrue(
            any(
                entry["relativePath"] == "schemas/extraction-record.json"
                and entry["classification"] == "legacy-excluded"
                for entry in payload["manifest"]["legacyArtifactPolicy"]
            )
        )
        self.assertIn("docs/architecture/capability_matrix.json", payload["manifest"]["capabilityMatrix"]["relativePath"])
        self.assertIn("/mcp/resources/contract-manifest", payload["manifest"]["resourceEndpoints"]["contractManifest"])
        self.assertIn("schemas/extraction-record.json", payload["manifest"]["legacyArtifactsExcluded"])

    def test_release_bundle_manifest_resource_exposes_whole_release_inventory(self) -> None:
        published = _load_json(RELEASE_BUNDLE_MANIFEST_PATH)
        payload = api_json("/mcp/resources/release-bundle-manifest")

        self.assertEqual(payload["contractVersion"], "pbpk-mcp.v1")
        self.assertEqual(payload["packageVersion"], published["packageVersion"])
        self.assertEqual(payload["sha256"], _sha256(RELEASE_BUNDLE_MANIFEST_PATH))
        self.assertEqual(payload["bundleSha256"], published["bundleSha256"])
        self.assertEqual(payload["relativePath"], "docs/architecture/release_bundle_manifest.json")
        self.assertEqual(payload["fileCount"], published["fileCount"])
        self.assertEqual(payload["totalBytes"], published["totalBytes"])
        self.assertIn("scripts/release_readiness_check.py", {entry["relativePath"] for entry in payload["manifest"]["files"]})
        self.assertIn("tests/test_runtime_security_live_stack.py", {entry["relativePath"] for entry in payload["manifest"]["files"]})

    def test_tool_catalog_exposes_documented_workflow(self) -> None:
        payload = api_json("/mcp/list_tools")
        tool_names = {tool["name"] for tool in payload["tools"]}

        expected = set(release_probe_required_tools())
        self.assertTrue(expected.issubset(tool_names))

        population_tool = next(tool for tool in payload["tools"] if tool["name"] == "run_population_simulation")
        required = set(population_tool["inputSchema"].get("required") or [])
        self.assertIn("simulationId", required)
        self.assertIn("cohort", required)
        self.assertNotIn(
            "modelPath",
            required,
            "run_population_simulation should operate on a loaded simulationId; modelPath is legacy-only",
        )

    def test_resource_endpoint_matches_discover_models_for_reference_model(self) -> None:
        resource_payload = api_json("/mcp/resources/models?search=reference_compound&backend=rxode2&limit=20")
        tool_payload = call_tool(
            {
                "tool": "discover_models",
                "arguments": {"search": "reference_compound", "backend": "rxode2", "limit": 20},
            }
        )["structuredContent"]

        resource_matches = [
            item
            for item in resource_payload["items"]
            if item["filePath"].endswith("reference_compound_population_rxode2_model.R")
        ]
        tool_matches = [
            item
            for item in tool_payload["items"]
            if item["filePath"].endswith("reference_compound_population_rxode2_model.R")
        ]

        self.assertTrue(resource_matches, "resource endpoint did not return the reference_compound model")
        self.assertTrue(tool_matches, "discover_models did not return the reference_compound model")

        resource_item = resource_matches[0]
        tool_item = tool_matches[0]
        self.assertEqual(resource_item["backend"], tool_item["backend"])
        self.assertEqual(resource_item["runtimeFormat"], tool_item["runtimeFormat"])
        self.assertEqual(resource_item["profileSource"], tool_item["profileSource"])
        self.assertEqual(resource_item["manifestStatus"], tool_item["manifestStatus"])
        self.assertEqual(resource_item["qualificationState"]["state"], tool_item["qualificationState"]["state"])
        self.assertEqual(
            resource_item["curationSummary"]["ngraDeclarationsExplicit"],
            tool_item["curationSummary"]["ngraDeclarationsExplicit"],
        )
        self.assertIn("trustSurfaceContract", tool_payload)
        self.assertEqual(tool_payload["trustSurfaceContract"]["tool"], "discover_models")
        self.assertEqual(tool_payload["trustSurfaceContract"]["surfaceCount"], 1)
        self.assertEqual(
            tool_payload["trustSurfaceContract"]["surfaces"][0]["surfacePath"],
            "items[*].curationSummary",
        )

    def test_wait_for_runtime_ready_script_succeeds_against_live_stack(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "scripts" / "wait_for_runtime_ready.py"),
                "--base-url",
                API_BASE_URL,
                "--auth-dev-secret",
                DEV_AUTH_SECRET,
                "--timeout-seconds",
                "15",
            ],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=LIVE_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["baseUrl"], API_BASE_URL)

    def test_workspace_model_smoke_script_succeeds_with_auth(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pbpk_live_smoke_") as tmp_dir:
            output_path = Path(tmp_dir) / "workspace_model_smoke.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(WORKSPACE_ROOT / "scripts" / "workspace_model_smoke.py"),
                    "--base-url",
                    API_BASE_URL,
                    "--search",
                    "reference_compound",
                    "--limit",
                    "1",
                    "--include-population",
                    "--auth-dev-secret",
                    DEV_AUTH_SECRET,
                    "--output",
                    str(output_path),
                ],
                cwd=WORKSPACE_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=LIVE_SUBPROCESS_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertTrue(payload["authConfigured"])
        self.assertEqual(payload["summary"]["totalModels"], 1)
        self.assertEqual(payload["summary"]["deterministicSucceeded"], 1)
        self.assertEqual(payload["summary"]["populationAttempted"], 1)
        self.assertEqual(payload["summary"]["populationSucceeded"], 1)

    def test_tool_discovers_new_workspace_model_file(self) -> None:
        model_name = f"autodiscovery_{uuid4().hex[:8]}.R"
        container_dir = "/app/var/models/discovery-tests"
        container_path = f"{container_dir}/{model_name}"
        with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False, encoding="utf-8") as handle:
            handle.write(
                "pbpk_default_parameters <- function() list(Test|Value = 1)\n"
                "pbpk_run_simulation <- function(parameters, simulation_id = NULL, run_id = NULL, request = list()) {\n"
                "  list(series = list(), metadata = list(sourceModel = basename(simulation_id %||% run_id %||% 'test')))\n"
                "}\n"
            )
            temp_path = Path(handle.name)
        try:
            subprocess.run(["docker", "exec", API_CONTAINER, "mkdir", "-p", container_dir], check=True)
            subprocess.run(["docker", "cp", str(temp_path), f"{API_CONTAINER}:{container_path}"], check=True)

            matches = []
            for _ in range(10):
                response = call_tool(
                    {
                        "tool": "discover_models",
                        "arguments": {"search": model_name, "limit": 20},
                    }
                )
                items = response["structuredContent"]["items"]
                matches = [item for item in items if item["filePath"].endswith(model_name)]
                if matches:
                    break
                time.sleep(0.2)

            self.assertTrue(matches, "newly added workspace model file was not discovered")

            item = matches[0]
            self.assertEqual(item["backend"], "rxode2")
            self.assertFalse(item["isLoaded"])
            self.assertEqual(item["discoveryState"], "discovered")
            self.assertEqual(item["manifestStatus"], "missing")
            self.assertEqual(item["qualificationState"]["state"], "exploratory")
            self.assertFalse(item["curationSummary"]["ngraDeclarationsExplicit"])
            self.assertIn("without model-specific static curation", item["curationSummary"]["reviewLabel"].lower())
        finally:
            temp_path.unlink(missing_ok=True)
            subprocess.run(
                ["docker", "exec", API_CONTAINER, "rm", "-f", container_path],
                check=False,
            )

    def test_tool_marks_reference_model_as_loaded_after_load(self) -> None:
        simulation_id = f"discover-live-ref-{uuid4().hex[:8]}"
        call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R",
                    "simulationId": simulation_id,
                },
            }
        )

        response = call_tool(
            {
                "tool": "discover_models",
                "arguments": {
                    "search": "reference_compound",
                    "backend": "rxode2",
                    "loadedOnly": True,
                    "limit": 20,
                },
            }
        )
        items = response["structuredContent"]["items"]
        matches = [
            item
            for item in items
            if item["filePath"].endswith("reference_compound_population_rxode2_model.R")
        ]
        self.assertTrue(matches, "loaded reference_compound model was not reported as loaded")
        loaded_ids = matches[0]["loadedSimulationIds"]
        self.assertIn(simulation_id, loaded_ids)

    def test_external_pbpk_ingestion_tool_normalizes_ngra_objects(self) -> None:
        response = call_tool(
            {
                "tool": "ingest_external_pbpk_bundle",
                "arguments": {
                    "sourcePlatform": "GastroPlus",
                    "sourceVersion": "10.1",
                    "modelName": "Imported example",
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
                    "pod": {
                        "ref": "pod-001",
                        "metric": "cmax",
                        "unit": "uM",
                        "source": "httr-benchmark",
                    },
                    "comparisonMetric": "cmax",
                },
            }
        )["structuredContent"]

        self.assertEqual(response["tool"], "ingest_external_pbpk_bundle")
        self.assertEqual(response["contractVersion"], "pbpk-mcp.v1")
        self.assertEqual(response["externalRun"]["sourcePlatform"], "GastroPlus")
        self.assertEqual(
            response["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertEqual(
            response["ngraObjects"]["pbpkQualificationSummary"]["assessmentBoundary"],
            "external-pbpk-normalization-only",
        )
        self.assertEqual(
            response["ngraObjects"]["pbpkQualificationSummary"]["reviewStatus"]["status"],
            "not-declared",
        )
        self.assertEqual(
            response["ngraObjects"]["uncertaintyHandoff"]["status"],
            "partial-pbpk-uncertainty-handoff",
        )
        self.assertEqual(
            response["ngraObjects"]["uncertaintyRegisterReference"]["status"],
            "not-attached",
        )
        self.assertEqual(
            response["ngraObjects"]["berInputBundle"]["status"],
            "ready-for-external-ber-calculation",
        )
        self.assertEqual(
            response["ngraObjects"]["pointOfDepartureReference"]["status"],
            "attached-external-reference",
        )
        self.assertEqual(
            response["ngraObjects"]["berInputBundle"]["decisionOwner"],
            "external-orchestrator",
        )


if __name__ == "__main__":
    unittest.main()
