from __future__ import annotations

import base64
from pathlib import Path

from mcp.tools.run_sensitivity_analysis import (
    RunSensitivityAnalysisRequest,
    run_sensitivity_analysis_tool,
)
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.services.job_service import JobService

FIXTURE_MODEL = Path("tests/fixtures/demo.pkml").resolve()


def test_run_sensitivity_analysis_tool_generates_report(tmp_path):
    adapter = InMemoryAdapter()
    adapter.init()
    job_service = JobService()

    try:
        request = RunSensitivityAnalysisRequest(
            modelPath=str(FIXTURE_MODEL),
            simulationId="sens-tool",
            parameters=[
                {
                    "path": "Organism|Weight",
                    "deltas": [-0.1, 0.1],
                    "baselineValue": 70.0,
                    "unit": "kg",
                }
            ],
        )

        response = run_sensitivity_analysis_tool(adapter, job_service, request)
        assert response.report["failures"] == []
        assert len(response.report["scenarios"]) == 3  # baseline + 2 deltas

        csv_attachment = response.csv
        csv_path = Path(csv_attachment.path)
        assert csv_path.exists()

        csv_bytes = base64.b64decode(csv_attachment.data.encode("ascii"))
        csv_text = csv_bytes.decode("utf-8")
        assert "scenario_id" in csv_text
        assert "sens-tool" in csv_attachment.filename

        # Clean up artefact to keep workspace tidy for repeated test runs.
        csv_path.unlink(missing_ok=True)
    finally:
        job_service.shutdown()
        adapter.shutdown()
