from __future__ import annotations

import json
import shutil
import subprocess
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


def api_json(path: str, payload: dict | None = None):
    url = f"{API_BASE_URL}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as resp:
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
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(f"{API_CONTAINER} is not available")

    def test_resource_endpoint_discovers_cisplatin(self) -> None:
        payload = api_json("/mcp/resources/models?search=cisplatin&limit=20")
        self.assertGreaterEqual(payload["total"], 1)

        matches = [
            item for item in payload["items"] if "cisplatin" in item["filePath"].lower()
        ]
        self.assertTrue(matches, "cisplatin model was not returned by /mcp/resources/models")

        item = matches[0]
        self.assertEqual(item["backend"], "rxode2")
        self.assertTrue(item["filePath"].endswith("cisplatin_population_rxode2_model.R"))
        self.assertEqual(item["runtimeFormat"], "r")
        self.assertIn(item["discoveryState"], {"discovered", "loaded"})

    def test_tool_catalog_exposes_documented_workflow(self) -> None:
        payload = api_json("/mcp/list_tools")
        tool_names = {tool["name"] for tool in payload["tools"]}

        expected = {
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

    def test_resource_endpoint_matches_discover_models_for_cisplatin(self) -> None:
        resource_payload = api_json("/mcp/resources/models?search=cisplatin&backend=rxode2&limit=20")
        tool_payload = call_tool(
            {
                "tool": "discover_models",
                "arguments": {"search": "cisplatin", "backend": "rxode2", "limit": 20},
            }
        )["structuredContent"]

        resource_matches = [
            item
            for item in resource_payload["items"]
            if item["filePath"].endswith("cisplatin_population_rxode2_model.R")
        ]
        tool_matches = [
            item
            for item in tool_payload["items"]
            if item["filePath"].endswith("cisplatin_population_rxode2_model.R")
        ]

        self.assertTrue(resource_matches, "resource endpoint did not return the cisplatin model")
        self.assertTrue(tool_matches, "discover_models did not return the cisplatin model")

        resource_item = resource_matches[0]
        tool_item = tool_matches[0]
        self.assertEqual(resource_item["backend"], tool_item["backend"])
        self.assertEqual(resource_item["runtimeFormat"], tool_item["runtimeFormat"])
        self.assertEqual(resource_item["profileSource"], tool_item["profileSource"])

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
        finally:
            temp_path.unlink(missing_ok=True)
            subprocess.run(
                ["docker", "exec", API_CONTAINER, "rm", "-f", container_path],
                check=False,
            )

    def test_tool_marks_cisplatin_as_loaded_after_load(self) -> None:
        simulation_id = f"discover-live-cis-{uuid4().hex[:8]}"
        call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
                    "simulationId": simulation_id,
                },
            }
        )

        response = call_tool(
            {
                "tool": "discover_models",
                "arguments": {
                    "search": "cisplatin",
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
            if item["filePath"].endswith("cisplatin_population_rxode2_model.R")
        ]
        self.assertTrue(matches, "loaded cisplatin model was not reported as loaded")
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
