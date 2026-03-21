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
        self.assertIn("ngraObjects", validation_payload)
        self.assertEqual(
            validation_payload["ngraObjects"]["assessmentContext"]["objectType"],
            "assessmentContext.v1",
        )
        self.assertEqual(
            validation_payload["ngraObjects"]["pbpkQualificationSummary"]["state"],
            "research-use",
        )
        self.assertEqual(
            validation_payload["ngraObjects"]["internalExposureEstimate"]["status"],
            "not-available",
        )
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

        verify_response = call_tool(
            {
                "tool": "run_verification_checks",
                "arguments": {
                    "simulationId": simulation_id,
                    "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
                },
            }
        )
        self.assertEqual(verify_response["status"], 200)

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
        self.assertIn("ngraObjects", report_payload)
        report = report_payload["report"]
        self.assertEqual(report["reportVersion"], "pbpk-oecd-report.v1")
        self.assertEqual(report["validation"]["assessment"]["decision"], "within-declared-guardrails")
        self.assertEqual(report["qualificationState"]["state"], "research-use")
        self.assertIn("ngraObjects", report)
        self.assertEqual(
            report_payload["ngraObjects"]["assessmentContext"]["objectType"],
            "assessmentContext.v1",
        )
        self.assertEqual(
            report_payload["ngraObjects"]["pbpkQualificationSummary"]["state"],
            "research-use",
        )
        self.assertEqual(
            report["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertIn(
            report["ngraObjects"]["internalExposureEstimate"]["selectionStatus"],
            {"explicit", "only-series", "unresolved"},
        )
        self.assertEqual(
            report["ngraObjects"]["berInputBundle"]["status"],
            "incomplete",
        )
        self.assertIn("modelPerformanceAndPredictivity", report["oecdChecklist"])
        self.assertEqual(report["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"], "partial")
        self.assertIn("softwarePlatformQualification", report["oecdChecklist"])
        self.assertEqual(report["oecdChecklist"]["softwarePlatformQualification"]["status"], "declared")
        self.assertEqual(report["performanceEvidence"]["included"], True)
        self.assertGreaterEqual(report["performanceEvidence"]["returnedRows"], 1)
        self.assertEqual(report["performanceEvidence"]["strongestEvidenceClass"], "runtime-smoke")
        self.assertEqual(
            report["performanceEvidence"]["qualificationBoundary"],
            "runtime-or-internal-evidence-only",
        )
        self.assertTrue(report["performanceEvidence"]["limitedToRuntimeOrInternalEvidence"])
        self.assertFalse(report["performanceEvidence"]["supportsObservedVsPredictedEvidence"])
        self.assertFalse(report["performanceEvidence"]["supportsPredictiveDatasetEvidence"])
        self.assertFalse(report["performanceEvidence"]["supportsExternalQualificationEvidence"])
        self.assertEqual(report["uncertaintyEvidence"]["included"], True)
        self.assertGreaterEqual(report["uncertaintyEvidence"]["returnedRows"], 1)
        self.assertEqual(
            report["profile"]["uncertainty"]["sensitivityAnalysis"]["status"],
            "local-screening-attached",
        )
        uncertainty_row_ids = {entry["id"] for entry in report["uncertaintyEvidence"]["rows"]}
        self.assertIn("bounded-variability-propagation-summary", uncertainty_row_ids)
        self.assertIn("local-sensitivity-screen-summary", uncertainty_row_ids)
        self.assertTrue(
            any(entry.startswith("bounded-variability-propagation-") for entry in uncertainty_row_ids)
        )
        self.assertTrue(
            any(entry.startswith("local-sensitivity-") for entry in uncertainty_row_ids)
        )
        self.assertEqual(report["verificationEvidence"]["included"], True)
        self.assertGreaterEqual(report["verificationEvidence"]["returnedRows"], 1)
        self.assertEqual(report["executableVerification"]["included"], True)
        self.assertEqual(report["executableVerification"]["status"], "passed")
        executable_check_ids = {entry["id"] for entry in report["executableVerification"]["checks"]}
        self.assertIn("parameter-unit-consistency", executable_check_ids)
        self.assertIn("systemic-flow-consistency", executable_check_ids)
        self.assertIn("renal-volume-consistency", executable_check_ids)
        self.assertIn("mass-balance", executable_check_ids)
        self.assertIn("solver-stability", executable_check_ids)
        self.assertEqual(report["platformQualificationEvidence"]["included"], True)
        self.assertGreaterEqual(report["platformQualificationEvidence"]["returnedRows"], 1)
        self.assertEqual(report["parameterTable"]["included"], True)
        self.assertLessEqual(report["parameterTable"]["returnedRows"], 5)
        self.assertGreater(report["parameterTable"]["matchedRows"], 0)

    def test_run_verification_checks_returns_structured_smoke_checks(self) -> None:
        simulation_id = f"oecd-live-verify-{uuid4().hex[:8]}"
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

        verify_response = call_tool(
            {
                "tool": "run_verification_checks",
                "arguments": {
                    "simulationId": simulation_id,
                    "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
                    "includePopulationSmoke": True,
                    "populationCohort": {"size": 10, "seed": 42},
                    "populationOutputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
                },
            }
        )
        self.assertEqual(verify_response["status"], 200)
        verify_payload = verify_response["body"]["structuredContent"]
        self.assertEqual(verify_payload["tool"], "run_verification_checks")
        self.assertEqual(verify_payload["contractVersion"], CONTRACT_VERSION)
        self.assertEqual(verify_payload["backend"], "rxode2")
        self.assertEqual(verify_payload["qualificationState"]["state"], "research-use")

        verification = verify_payload["verification"]
        self.assertEqual(verification["status"], "passed")
        self.assertTrue(verification["requestedPopulationSmoke"])
        check_ids = {entry["id"] for entry in verification["checks"]}
        self.assertTrue(
            {
                "preflight-validation",
                "parameter-catalog",
                "verification-evidence",
                "deterministic-smoke",
                "deterministic-integrity",
                "deterministic-reproducibility",
                "parameter-unit-consistency",
                "systemic-flow-consistency",
                "renal-volume-consistency",
                "mass-balance",
                "solver-stability",
                "population-smoke",
            }.issubset(check_ids)
        )

        deterministic_check = next(
            entry for entry in verification["checks"] if entry["id"] == "deterministic-smoke"
        )
        self.assertEqual(deterministic_check["status"], "passed")
        self.assertGreaterEqual(deterministic_check["seriesCount"], 1)
        self.assertTrue(deterministic_check["resultsId"])

        integrity_check = next(
            entry for entry in verification["checks"] if entry["id"] == "deterministic-integrity"
        )
        self.assertEqual(integrity_check["status"], "passed")

        reproducibility_check = next(
            entry for entry in verification["checks"] if entry["id"] == "deterministic-reproducibility"
        )
        self.assertEqual(reproducibility_check["status"], "passed")
        self.assertGreaterEqual(reproducibility_check["comparedPointCount"], 1)

        unit_consistency_check = next(
            entry for entry in verification["checks"] if entry["id"] == "parameter-unit-consistency"
        )
        self.assertEqual(unit_consistency_check["status"], "passed")

        flow_consistency_check = next(
            entry for entry in verification["checks"] if entry["id"] == "systemic-flow-consistency"
        )
        self.assertEqual(flow_consistency_check["status"], "passed")

        volume_consistency_check = next(
            entry for entry in verification["checks"] if entry["id"] == "renal-volume-consistency"
        )
        self.assertEqual(volume_consistency_check["status"], "passed")

        mass_balance_check = next(
            entry for entry in verification["checks"] if entry["id"] == "mass-balance"
        )
        self.assertEqual(mass_balance_check["status"], "passed")

        solver_stability_check = next(
            entry for entry in verification["checks"] if entry["id"] == "solver-stability"
        )
        self.assertEqual(solver_stability_check["status"], "passed")

        population_check = next(
            entry for entry in verification["checks"] if entry["id"] == "population-smoke"
        )
        self.assertEqual(population_check["status"], "passed")
        self.assertGreaterEqual(population_check["aggregateCount"], 1)
        self.assertTrue(population_check["resultsId"])

        deterministic_results = call_tool(
            {"tool": "get_results", "arguments": {"resultsId": deterministic_check["resultsId"]}}
        )
        self.assertEqual(deterministic_results["status"], 200)
        self.assertGreaterEqual(
            len(deterministic_results["body"]["structuredContent"]["series"]),
            1,
        )

    def test_population_run_uses_loaded_simulation_id_without_model_path(self) -> None:
        simulation_id = f"oecd-live-pop-{uuid4().hex[:8]}"
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

        submit_response = call_tool(
            {
                "tool": "run_population_simulation",
                "critical": True,
                "arguments": {
                    "simulationId": simulation_id,
                    "cohort": {"size": 10, "seed": 42},
                    "outputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
                },
            }
        )
        self.assertEqual(submit_response["status"], 200)
        payload = submit_response["body"]["structuredContent"]
        self.assertEqual(payload["simulationId"], simulation_id)

        result_id = None
        for _ in range(20):
            time.sleep(1)
            status_response = call_tool(
                {"tool": "get_job_status", "arguments": {"jobId": payload["jobId"]}}
            )
            self.assertEqual(status_response["status"], 200)
            job_payload = status_response["body"]["structuredContent"]
            if job_payload["status"] == "succeeded":
                result_id = job_payload["resultId"]
                break
        self.assertIsNotNone(result_id, "population simulation did not finish successfully")

        population_results = call_tool(
            {"tool": "get_population_results", "arguments": {"resultsId": result_id}}
        )
        self.assertEqual(population_results["status"], 200)
        results_payload = population_results["body"]["structuredContent"]
        self.assertGreaterEqual(len(results_payload.get("aggregates") or {}), 1)

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
