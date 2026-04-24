from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.services.cross_parameter_consistency import CrossParameterConsistencyValidator
from mcp_bridge.pbpk_tools.run_parameter_consistency_check import (
    RunParameterConsistencyCheckRequest,
    run_parameter_consistency_check,
)


class RunParameterConsistencyCheckTests(unittest.TestCase):
    def _setup_consistent_sim(self) -> InMemoryAdapter:
        adapter = InMemoryAdapter()
        adapter.init()
        adapter.load_simulation("/tmp/test.pkml", simulation_id="sim-1")
        defaults = {
            "Organism|Weight": (70.0, "kg"),
            "Organism|CardiacOutput": (5.0, "L/min"),
            "Organism|Liver|Volume": (1.5, "L"),
            "Organism|Kidney|Volume": (0.3, "L"),
            "Organism|Brain|Volume": (1.4, "L"),
            "Organism|Muscle|Volume": (24.0, "L"),
            "Organism|AdiposeTissue|Volume": (15.0, "L"),
            "Organism|Liver|BloodFlow": (1.0, "L/min"),
            "Organism|Kidney|BloodFlow": (1.0, "L/min"),
            "Organism|Brain|BloodFlow": (0.7, "L/min"),
            "Organism|Liver|Clearance": (30.0, "L/h"),
        }
        for path, (value, unit) in defaults.items():
            adapter.set_parameter_value("sim-1", path, value, unit)
        return adapter

    def _setup_inconsistent_sim(self) -> InMemoryAdapter:
        adapter = InMemoryAdapter()
        adapter.init()
        adapter.load_simulation("/tmp/test.pkml", simulation_id="sim-bad")
        defaults = {
            "Organism|Weight": (5.0, "kg"),
            "Organism|CardiacOutput": (1.0, "L/min"),
            "Organism|Liver|Volume": (2.0, "L"),
            "Organism|Kidney|Volume": (0.5, "L"),
            "Organism|Brain|Volume": (1.5, "L"),
            "Organism|Muscle|Volume": (3.0, "L"),
            "Organism|AdiposeTissue|Volume": (2.0, "L"),
            "Organism|Liver|BloodFlow": (0.5, "L/min"),
            "Organism|Kidney|BloodFlow": (0.4, "L/min"),
            "Organism|Brain|BloodFlow": (0.3, "L/min"),
            "Organism|Liver|Clearance": (120.0, "L/h"),
        }
        for path, (value, unit) in defaults.items():
            adapter.set_parameter_value("sim-bad", path, value, unit)
        return adapter

    def test_validate_all_returns_ok_for_consistent_model(self) -> None:
        adapter = self._setup_consistent_sim()
        request = RunParameterConsistencyCheckRequest(simulation_id="sim-1")
        response = run_parameter_consistency_check(adapter, request)
        self.assertTrue(response.ok)
        self.assertEqual(response.violation_count, 0)
        self.assertEqual(len(response.violations), 0)
        self.assertIn("passed", response.summary.lower())
        self.assertIn("organ_volumes_vs_body_weight", response.checked_rules)
        self.assertIn("organ_blood_flows_vs_cardiac_output", response.checked_rules)
        self.assertIn("hepatic_clearance_vs_blood_flow", response.checked_rules)

    def test_validate_all_detects_multiple_violations(self) -> None:
        adapter = self._setup_inconsistent_sim()
        request = RunParameterConsistencyCheckRequest(simulation_id="sim-bad")
        response = run_parameter_consistency_check(adapter, request)
        self.assertFalse(response.ok)
        self.assertGreaterEqual(response.violation_count, 1)
        self.assertGreaterEqual(len(response.violations), 1)

    def test_validate_all_gracefully_handles_missing_parameters(self) -> None:
        adapter = InMemoryAdapter()
        adapter.init()
        adapter.load_simulation("/tmp/test.pkml", simulation_id="sim-empty")
        request = RunParameterConsistencyCheckRequest(simulation_id="sim-empty")
        response = run_parameter_consistency_check(adapter, request)
        self.assertTrue(response.ok)
        self.assertEqual(response.violation_count, 0)

    def test_tool_response_models_are_serializable(self) -> None:
        adapter = self._setup_consistent_sim()
        request = RunParameterConsistencyCheckRequest(simulation_id="sim-1")
        response = run_parameter_consistency_check(adapter, request)
        data = response.model_dump(by_alias=True)
        self.assertEqual(data["tool"], "run_parameter_consistency_check")
        self.assertEqual(data["simulationId"], "sim-1")


if __name__ == "__main__":
    unittest.main()
