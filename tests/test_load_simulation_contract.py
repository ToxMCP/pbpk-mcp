from __future__ import annotations

import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
LOAD_SIMULATION_TOOL = WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "load_simulation.py"


class LoadSimulationContractTests(unittest.TestCase):
    def test_load_simulation_source_rejects_pksim5_with_export_guidance(self) -> None:
        source = LOAD_SIMULATION_TOOL.read_text(encoding="utf-8")
        self.assertIn("Direct .pksim5 loading is not supported", source)
        self.assertIn("export the PK-Sim project to .pkml first", source)

    def test_load_simulation_source_rejects_mmd_with_conversion_guidance(self) -> None:
        source = LOAD_SIMULATION_TOOL.read_text(encoding="utf-8")
        self.assertIn("Direct Berkeley Madonna .mmd loading is not supported", source)
        self.assertIn("convert the model to .pkml or an MCP-ready .R module first", source)


if __name__ == "__main__":
    unittest.main()
