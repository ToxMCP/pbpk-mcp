from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.adapter.schema import ParameterValue
from mcp_bridge.services.cross_parameter_consistency import CrossParameterConsistencyValidator


class CrossParameterConsistencyTests(unittest.TestCase):
    def _setup_sim(self) -> InMemoryAdapter:
        adapter = InMemoryAdapter()
        adapter.init()
        adapter.load_simulation("/tmp/test.pkml", simulation_id="sim-1")
        # Seed baseline consistent parameters
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
            "Organism|Liver|Clearance": (30.0, "L/h"),  # 0.5 L/min
        }
        for path, (value, unit) in defaults.items():
            adapter.set_parameter_value("sim-1", path, value, unit)
        return adapter

    def test_organ_volume_sum_exceeds_body_weight_is_rejected(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        # Increase adipose volume so total exceeds 70 kg
        ok, violations = validator.validate("Organism|AdiposeTissue|Volume", 50.0)
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertIn("Total organ volume", violations[0])
        self.assertIn("exceeds body weight", violations[0])

    def test_organ_volume_sum_within_body_weight_is_accepted(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|AdiposeTissue|Volume", 10.0)
        self.assertTrue(ok)
        self.assertEqual(len(violations), 0)

    def test_blood_flow_sum_exceeds_cardiac_output_is_rejected(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|Brain|BloodFlow", 5.0)
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertIn("Total organ blood flow", violations[0])
        self.assertIn("exceeds cardiac output", violations[0])

    def test_blood_flow_sum_within_cardiac_output_is_accepted(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|Brain|BloodFlow", 0.5)
        self.assertTrue(ok)
        self.assertEqual(len(violations), 0)

    def test_hepatic_clearance_exceeds_blood_flow_is_rejected(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        # 120 L/h = 2.0 L/min, which exceeds hepatic blood flow of 1.0 L/min
        ok, violations = validator.validate("Organism|Liver|Clearance", 120.0, "L/h")
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertIn("Hepatic clearance", violations[0])
        self.assertIn("exceeds hepatic blood flow", violations[0])

    def test_hepatic_clearance_within_blood_flow_is_accepted(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|Liver|Clearance", 30.0, "L/h")
        self.assertTrue(ok)
        self.assertEqual(len(violations), 0)

    def test_missing_related_parameters_are_gracefully_skipped(self) -> None:
        adapter = InMemoryAdapter()
        adapter.init()
        adapter.load_simulation("/tmp/test.pkml", simulation_id="sim-empty")
        # Only set a liver volume; no body weight or other organs
        adapter.set_parameter_value("sim-empty", "Organism|Liver|Volume", 10.0, "L")
        validator = CrossParameterConsistencyValidator(adapter, "sim-empty")
        ok, violations = validator.validate("Organism|Liver|Volume", 10.0)
        self.assertTrue(ok)
        self.assertEqual(len(violations), 0)

    def test_unit_conversion_for_flow(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        # Cardiac output = 5 L/min = 5000 mL/min
        ok, violations = validator.validate("Organism|Brain|BloodFlow", 6000.0, "mL/min")
        self.assertFalse(ok)
        self.assertIn("exceeds cardiac output", violations[0])

    def test_unit_conversion_for_clearance(self) -> None:
        adapter = self._setup_sim()
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        # Liver blood flow = 1.0 L/min. 90 L/h = 1.5 L/min -> exceeds.
        ok, violations = validator.validate("Organism|Liver|Clearance", 90.0, "L/h")
        self.assertFalse(ok)
        self.assertIn("exceeds hepatic blood flow", violations[0])

    def test_new_organs_included_in_volume_sum(self) -> None:
        adapter = self._setup_sim()
        # Add heart and lung volumes so baseline is consistent but close to limit
        adapter.set_parameter_value("sim-1", "Organism|Heart|Volume", 0.3, "L")
        adapter.set_parameter_value("sim-1", "Organism|Lung|Volume", 1.0, "L")
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|Heart|Volume", 30.0)
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertIn("Total organ volume", violations[0])
        self.assertIn("Heart volume", violations[0])
        self.assertIn("Lung volume", violations[0])

    def test_new_organs_included_in_flow_sum(self) -> None:
        adapter = self._setup_sim()
        # Add pulmonary and coronary flows
        adapter.set_parameter_value("sim-1", "Organism|Heart|BloodFlow", 0.2, "L/min")
        adapter.set_parameter_value("sim-1", "Organism|Lung|BloodFlow", 4.0, "L/min")
        validator = CrossParameterConsistencyValidator(adapter, "sim-1")
        ok, violations = validator.validate("Organism|Lung|BloodFlow", 6.0)
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertIn("Total organ blood flow", violations[0])
        self.assertIn("Pulmonary blood flow", violations[0])
        self.assertIn("Coronary blood flow", violations[0])


if __name__ == "__main__":
    unittest.main()
