#!/usr/bin/env python3
"""Compare benchmark results against baseline thresholds and emit CI-friendly output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _percent_delta(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return ((actual - expected) / expected) * 100.0


def _format_ms(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "n/a"


def _build_table(rows: List[Tuple[str, float | None, float, float, str]]) -> str:
    lines = ["| Step | p95 (ms) | Baseline p95 (ms) | Δ% | Status |", "| --- | --- | --- | --- | --- |"]
    for step, actual, expected, delta, status in rows:
        actual_str = _format_ms(actual)
        delta_str = f"{delta:+.2f}" if delta != float("inf") else "inf"
        lines.append(f"| `{step}` | {actual_str} | {_format_ms(expected)} | {delta_str} | {status} |")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check benchmark regression against baseline thresholds.")
    parser.add_argument("--benchmark", required=True, help="Path to the benchmark JSON emitted by the harness.")
    parser.add_argument("--baseline", required=True, help="Threshold JSON containing expected p95 values.")
    parser.add_argument(
        "--summary-output",
        default=None,
        help="Optional path to write Markdown summary (also printed to stdout).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    benchmark_path = Path(args.benchmark).resolve()
    baseline_path = Path(args.baseline).resolve()
    summary_path = Path(args.summary_output).resolve() if args.summary_output else None

    benchmark = _load_json(benchmark_path)
    baseline = _load_json(baseline_path)

    tolerance_pct = float(baseline.get("regressionTolerancePercent", 10.0))
    allowed_factor = 1.0 + tolerance_pct / 100.0

    steps_actual = benchmark.get("steps", {})
    baseline_steps = baseline.get("steps", {})
    table_rows: List[Tuple[str, float | None, float, float, str]] = []
    failures: List[str] = []

    for step, expectations in baseline_steps.items():
        expected_p95 = float(expectations.get("p95", 0.0))
        actual_entry = steps_actual.get(step)
        actual_p95 = None
        if isinstance(actual_entry, dict):
            value = actual_entry.get("p95")
            if isinstance(value, (int, float)):
                actual_p95 = float(value)
        if actual_p95 is None:
            failures.append(f"Missing p95 metric for step '{step}' in benchmark {benchmark_path.name}")
            table_rows.append((step, None, expected_p95, float("inf"), "MISSING"))
            continue

        delta_pct = _percent_delta(actual_p95, expected_p95)
        status = "PASS"
        if actual_p95 > expected_p95 * allowed_factor:
            status = "FAIL"
            failures.append(
                f"{step} p95 {actual_p95:.3f}ms exceeds baseline {expected_p95:.3f}ms by {delta_pct:.2f}% "
                f"(tolerance {tolerance_pct:.1f}%)"
            )
        table_rows.append((step, actual_p95, expected_p95, delta_pct, status))

    # Optional overall summary comparison
    baseline_summary = baseline.get("summary", {})
    benchmark_summary = benchmark.get("summary", {})
    if "p95" in baseline_summary:
        expected = float(baseline_summary["p95"])
        actual = float(benchmark_summary.get("p95", expected))
        delta_pct = _percent_delta(actual, expected)
        status = "PASS"
        if actual > expected * allowed_factor:
            status = "FAIL"
            failures.append(
                f"Overall p95 {actual:.3f}ms exceeds baseline {expected:.3f}ms by {delta_pct:.2f}% "
                f"(tolerance {tolerance_pct:.1f}%)"
            )
        table_rows.append(("__overall__", actual, expected, delta_pct, status))

    summary_md = [
        f"**Benchmark:** `{benchmark_path.name}`",
        f"**Baseline:** `{baseline_path}`",
        f"**Tolerance:** ±{tolerance_pct:.1f}% over baseline p95\n",
        _build_table(table_rows),
    ]

    if summary_path:
        summary_path.write_text("\n\n".join(summary_md) + "\n", encoding="utf-8")
    print("\n\n".join(summary_md))

    if failures:
        print("\nFailures:\n- " + "\n- ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
