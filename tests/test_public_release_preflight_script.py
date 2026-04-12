from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "public_release_preflight.py"
spec = importlib.util.spec_from_file_location("pbpk_public_release_preflight", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_public_release_preflight", module)
spec.loader.exec_module(module)


class PublicReleasePreflightScriptTests(unittest.TestCase):
    def test_build_auth_args_prefers_bearer_token(self) -> None:
        args = module.build_auth_args(
            bearer_token="token-123",
            auth_dev_secret="ignored-secret",
        )

        self.assertEqual(args, ["--bearer-token", "token-123"])

    def test_build_preflight_plan_includes_expected_default_steps(self) -> None:
        args = module.parse_args([])
        plan = module.build_preflight_plan(args)

        self.assertEqual(
            [step.name for step in plan],
            [
                "runtime_ready",
                "runtime_contract_test",
                "release_readiness_check",
                "live_stack_tests",
                "workspace_smoke_deterministic",
                "workspace_smoke_population",
                "review_signoff_index_dry_run",
            ],
        )
        self.assertIn("scripts/release_readiness_check.py", plan[2].command)
        self.assertIn("tests/test_oecd_live_stack.py", plan[3].command)
        self.assertEqual(
            Path(plan[2].output_path),
            WORKSPACE_ROOT / "var" / "release_readiness_summary.json",
        )

    def test_build_preflight_plan_respects_skip_flags(self) -> None:
        args = module.parse_args([])
        args.skip_runtime_ready = True
        args.skip_runtime_contract = True
        args.skip_signoff_backfill_dry_run = True
        args.audit_path = "s3://pbpk-mcp-audit-smoke/review"
        plan = module.build_preflight_plan(args)

        self.assertEqual(
            [step.name for step in plan],
            [
                "release_readiness_check",
                "live_stack_tests",
                "workspace_smoke_deterministic",
                "workspace_smoke_population",
            ],
        )

    def test_run_step_writes_json_stdout_summary_file_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "summary.json"
            step = module.StepSpec(
                name="json_stdout_step",
                command=(
                    sys.executable,
                    "-c",
                    "import json; print(json.dumps({'status': 'ok', 'count': 2}))",
                ),
                timeout_seconds=30,
                summary_kind="json_stdout",
                output_path=output_path,
            )

            record = module.run_step(step)

            self.assertEqual(record["summary"]["status"], "ok")
            self.assertEqual(record["summaryPath"], str(output_path))
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                {"status": "ok", "count": 2},
            )


if __name__ == "__main__":
    unittest.main()
