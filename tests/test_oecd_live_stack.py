from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import time
import unittest
from uuid import uuid4


API_CONTAINER = "pbpk_mcp-api-1"
CONTRACT_VERSION = "pbpk-mcp.v1"
PKSIM5_PROJECT = "/app/var/demos/cimetidine/Cimetidine-Model.pksim5"


def docker_exec_json(script: str):
    completed = subprocess.run(
        ["docker", "exec", API_CONTAINER, "python", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip() or "null")


def call_tool(payload: dict):
    script = textwrap.dedent(
        f"""
        import json
        import urllib.error
        import urllib.request

        payload = json.loads({json.dumps(json.dumps(payload))})
        req = urllib.request.Request(
            "http://127.0.0.1:8000/mcp/call_tool",
            data=json.dumps(payload).encode(),
            headers={{"content-type": "application/json"}},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode())
                print(json.dumps({{"status": resp.status, "body": body}}))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {{"raw": body}}
            print(json.dumps({{"status": exc.code, "body": parsed}}))
        """
    )
    return docker_exec_json(script)


@unittest.skipUnless(shutil.which("docker"), "docker is required for live-stack OECD tests")
class OecdLiveStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        probe = subprocess.run(
            ["docker", "exec", API_CONTAINER, "true"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(f"{API_CONTAINER} is not available")

    def test_cisplatin_scalar_context_validation(self) -> None:
        simulation_id = f"oecd-live-cis-{uuid4().hex[:8]}"
        load_response = call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
                    "simulationId": simulation_id,
                },
            }
        )
        self.assertEqual(load_response["status"], 200)
        load_payload = load_response["body"]["structuredContent"]
        self.assertEqual(load_payload["tool"], "load_simulation")
        self.assertEqual(load_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(load_payload["backend"], "rxode2")

        validation_response = call_tool(
            {
                "tool": "validate_simulation_request",
                "arguments": {
                    "simulationId": simulation_id,
                    "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
                },
            }
        )
        self.assertEqual(validation_response["status"], 200)
        validation_payload = validation_response["body"]["structuredContent"]
        self.assertEqual(validation_payload["tool"], "validate_simulation_request")
        self.assertEqual(validation_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(validation_payload["backend"], "rxode2")
        self.assertEqual(validation_payload["qualificationState"]["state"], "research-use")
        validation = validation_payload["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["assessment"]["decision"], "within-declared-guardrails")
        self.assertEqual(validation["assessment"]["oecdReadiness"], "research-use")

    def test_pregnancy_sidecar_rejects_regulatory_use(self) -> None:
        simulation_id = f"oecd-live-preg-{uuid4().hex[:8]}"
        load_response = call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml",
                    "simulationId": simulation_id,
                },
            }
        )
        self.assertEqual(load_response["status"], 200)
        load_payload = load_response["body"]["structuredContent"]
        self.assertEqual(load_payload["tool"], "load_simulation")
        self.assertEqual(load_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(load_payload["backend"], "ospsuite")

        validation_response = call_tool(
            {
                "tool": "validate_simulation_request",
                "arguments": {
                    "simulationId": simulation_id,
                    "request": {"contextOfUse": "regulatory-use"},
                },
            }
        )
        self.assertEqual(validation_response["status"], 200)
        validation_payload = validation_response["body"]["structuredContent"]
        self.assertEqual(validation_payload["tool"], "validate_simulation_request")
        self.assertEqual(validation_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(validation_payload["backend"], "ospsuite")
        validation = validation_payload["validation"]
        self.assertFalse(validation["ok"])
        self.assertEqual(validation["assessment"]["decision"], "outside-declared-profile")
        error_codes = {entry["code"] for entry in validation["errors"]}
        self.assertIn("context_of_use_mismatch", error_codes)

    def test_export_oecd_report_returns_profile_and_parameter_table(self) -> None:
        simulation_id = f"oecd-live-report-{uuid4().hex[:8]}"
        load_response = call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
                    "simulationId": simulation_id,
                },
            }
        )
        self.assertEqual(load_response["status"], 200)

        report_response = call_tool(
            {
                "tool": "export_oecd_report",
                "arguments": {
                    "simulationId": simulation_id,
                    "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
                    "parameterLimit": 5,
                },
            }
        )
        self.assertEqual(report_response["status"], 200)
        report_payload = report_response["body"]["structuredContent"]
        self.assertEqual(report_payload["tool"], "export_oecd_report")
        self.assertEqual(report_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(report_payload["backend"], "rxode2")
        self.assertEqual(report_payload["qualificationState"]["state"], "research-use")
        report = report_payload["report"]
        self.assertEqual(report["reportVersion"], "pbpk-oecd-report.v1")
        self.assertEqual(report["validation"]["assessment"]["decision"], "within-declared-guardrails")
        self.assertEqual(report["qualificationState"]["state"], "research-use")
        self.assertIn("modelPerformanceAndPredictivity", report["oecdChecklist"])
        self.assertEqual(report["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"], "partial")
        self.assertEqual(report["performanceEvidence"]["included"], True)
        self.assertGreaterEqual(report["performanceEvidence"]["returnedRows"], 1)
        self.assertEqual(report["parameterTable"]["included"], True)
        self.assertLessEqual(report["parameterTable"]["returnedRows"], 5)
        self.assertGreater(report["parameterTable"]["matchedRows"], 0)

    def test_validate_model_manifest_reports_static_manifest_state(self) -> None:
        response = call_tool(
            {
                "tool": "validate_model_manifest",
                "arguments": {
                    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
                },
            }
        )
        self.assertEqual(response["status"], 200)
        payload = response["body"]["structuredContent"]
        self.assertEqual(payload["tool"], "validate_model_manifest")
        self.assertEqual(payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(payload["backend"], "rxode2")
        manifest = payload["manifest"]
        self.assertEqual(manifest["validationMode"], "static-manifest-inspection")
        self.assertEqual(manifest["qualificationState"]["state"], "research-use")
        self.assertTrue(manifest["hooks"]["modelProfile"])

    def test_load_simulation_rejects_pksim5_with_export_guidance(self) -> None:
        response = call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": PKSIM5_PROJECT,
                    "simulationId": f"pksim5-live-{uuid4().hex[:8]}",
                },
            }
        )
        self.assertEqual(response["status"], 400)
        message = json.dumps(response["body"])
        self.assertIn("Direct .pksim5 loading is not supported", message)
        self.assertIn("export the PK-Sim project to .pkml first", message)

    def test_async_results_preserve_oecd_validation_metadata(self) -> None:
        simulation_id = f"oecd-live-run-{uuid4().hex[:8]}"
        run_id = f"{simulation_id}-result"

        load_response = call_tool(
            {
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
                    "simulationId": simulation_id,
                },
            }
        )
        self.assertEqual(load_response["status"], 200)
        load_payload = load_response["body"]["structuredContent"]
        self.assertEqual(load_payload["tool"], "load_simulation")
        self.assertEqual(load_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(load_payload["backend"], "rxode2")

        run_response = call_tool(
            {
                "tool": "run_simulation",
                "critical": True,
                "arguments": {"simulationId": simulation_id, "runId": run_id},
            }
        )
        self.assertEqual(run_response["status"], 200)
        job_id = run_response["body"]["structuredContent"]["jobId"]

        result_id = None
        for _ in range(20):
            time.sleep(1)
            status_response = call_tool(
                {"tool": "get_job_status", "arguments": {"jobId": job_id}}
            )
            self.assertEqual(status_response["status"], 200)
            status_payload = status_response["body"]["structuredContent"]
            self.assertEqual(status_payload["tool"], "get_job_status")
            self.assertEqual(status_payload["contractVersion"], CONTRACT_VERSION)
            self.assertEqual(status_payload["jobId"], job_id)
            self.assertIn("job", status_payload)
            self.assertEqual(status_payload["job"]["jobId"], job_id)
            if status_payload["status"] == "succeeded":
                result_id = status_payload["resultId"]
                self.assertEqual(
                    status_payload["resultHandle"]["resultsId"],
                    result_id,
                )
                break

        self.assertIsNotNone(result_id, "asynchronous simulation did not complete in time")

        results_response = call_tool(
            {"tool": "get_results", "arguments": {"resultsId": result_id}}
        )
        self.assertEqual(results_response["status"], 200)
        result = results_response["body"]["structuredContent"]

        self.assertEqual(result["tool"], "get_results")
        self.assertEqual(result["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(result["backend"], "rxode2")
        self.assertEqual(result["resultsId"], result_id)
        self.assertEqual(len(result["series"]), 5)
        self.assertEqual(
            result["metadata"]["validation"]["assessment"]["decision"],
            "within-declared-guardrails",
        )
        self.assertEqual(
            result["metadata"]["validation"]["assessment"]["oecdReadiness"],
            "research-use",
        )


if __name__ == "__main__":
    unittest.main()
