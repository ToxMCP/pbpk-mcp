"""Performance regression gate.

This test is intentionally skipped unless the CI pipeline provides paths to
fresh benchmark JSON artefacts via environment variables. When enabled it
invokes the existing regression checker under ``scripts/`` and fails the build
if any metric breaches the baseline thresholds.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.perf
def test_benchmark_thresholds() -> None:
    """Validate benchmark results against the recorded baseline."""

    result_path = os.getenv("MCP_BENCHMARK_RESULT")
    if not result_path:
        pytest.skip("Set MCP_BENCHMARK_RESULT to enable performance gating.")

    benchmark = Path(result_path)
    assert benchmark.exists(), f"Benchmark JSON not found at {benchmark}"

    baseline_path = os.getenv("MCP_BENCHMARK_BASELINE", "benchmarks/thresholds/smoke.json")
    baseline = Path(baseline_path)
    assert baseline.exists(), f"Baseline JSON not found at {baseline}"

    cmd = [
        sys.executable,
        "scripts/check_benchmark_regression.py",
        "--benchmark",
        str(benchmark),
        "--baseline",
        str(baseline),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    message = completed.stdout + completed.stderr
    assert completed.returncode == 0, f"Benchmark regression detected:\n{message}"
