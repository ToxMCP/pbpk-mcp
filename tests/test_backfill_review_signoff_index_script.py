from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "backfill_review_signoff_index.py"
spec = importlib.util.spec_from_file_location("pbpk_backfill_review_signoff_index", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_backfill_review_signoff_index", module)
spec.loader.exec_module(module)


class BackfillReviewSignoffIndexScriptTests(unittest.TestCase):
    def test_main_backfills_local_legacy_signoff_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event = {
                "eventId": "legacy-script-event",
                "timestamp": "2026-04-08T12:34:56+00:00",
                "eventType": "review.signoff.recorded",
                "previousHash": "0" * 64,
                "hash": "deadbeef",
                "identity": {"subject": "script-operator", "roles": ["operator"]},
                "reviewSignoff": {
                    "simulationId": "legacy-script",
                    "scope": "export_oecd_report",
                    "disposition": "acknowledged",
                    "rationale": "Backfill script should rebuild the missing index entry.",
                    "serviceVersion": "0.4.2",
                },
            }
            path = Path(tmpdir) / "2026" / "04" / "08.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            with mock.patch.object(
                sys,
                "argv",
                ["backfill_review_signoff_index.py", tmpdir],
            ):
                with mock.patch("builtins.print") as print_mock:
                    exit_code = module.main()

            self.assertEqual(exit_code, 0)
            printed = json.loads(print_mock.call_args.args[0])
            self.assertEqual(printed["backend"], "local")
            self.assertEqual(printed["signoffEvents"], 1)
            self.assertEqual(printed["indexedNew"], 1)
            index_dir = Path(tmpdir) / "_index" / "review_signoff"
            self.assertTrue(any(index_dir.glob("*/*.json")))


if __name__ == "__main__":
    unittest.main()
