from __future__ import annotations

from pathlib import Path

from mcp_bridge.parity.suite import ParitySuiteError, run_parity_suite


def test_run_parity_suite_passes(tmp_path, monkeypatch):
    result = run_parity_suite(iterations=2)
    assert result.ok
    assert result.max_delta_percent <= result.tolerance_percent


def test_run_parity_suite_detects_missing_model(tmp_path, monkeypatch):
    bad_cases = tmp_path / "cases.json"
    bad_cases.write_text(
        """
        {
            "tolerancePercent": 1.0,
            "cases": [
                {
                    "id": "missing",
                    "name": "Missing Model",
                    "modelPath": "reference/models/standard/missing-file.pkml",
                    "sha256": "deadbeef",
                    "expectedMetrics": []
                }
            ]
        }
        """,
        encoding="utf-8",
    )

    try:
        run_parity_suite(iterations=1, cases_path=bad_cases)
    except ParitySuiteError:
        return

    raise AssertionError("ParitySuiteError was not raised for missing model")
