from __future__ import annotations

from pathlib import Path

import pytest

from mcp.tools.load_simulation import (
    LoadSimulationRequest,
    LoadSimulationValidationError,
    resolve_model_path,
    validate_load_simulation_request,
)

def test_resolve_model_path_accepts_pksim5(tmp_path: Path) -> None:
    # Create a dummy .pksim5 file
    model_file = tmp_path / "model.pksim5"
    model_file.write_text("<pksim5 />")
    
    # It should pass validation when the root is allowed
    resolved = resolve_model_path(str(model_file), allowed_roots=[tmp_path])
    assert resolved == model_file

def test_resolve_model_path_accepts_pkml(tmp_path: Path) -> None:
    # Create a dummy .pkml file
    model_file = tmp_path / "model.pkml"
    model_file.write_text("<pkml />")
    
    # It should pass validation when the root is allowed
    resolved = resolve_model_path(str(model_file), allowed_roots=[tmp_path])
    assert resolved == model_file

def test_validate_load_simulation_request_with_pksim5(tmp_path: Path) -> None:
    model_file = tmp_path / "test_model.pksim5"
    model_file.write_text("<pksim5 />")
    
    payload = LoadSimulationRequest(filePath=str(model_file))
    
    simulation_id, resolved = validate_load_simulation_request(
        payload,
        allowed_roots=[tmp_path],
    )
    
    assert simulation_id == "test_model"
    assert resolved == model_file

def test_resolve_model_path_rejects_other_extensions(tmp_path: Path) -> None:
    bad_file = tmp_path / "model.txt"
    bad_file.write_text("content")

    with pytest.raises(LoadSimulationValidationError) as exc:
        resolve_model_path(str(bad_file), allowed_roots=[tmp_path])
    
    assert "Only .pkml and .pksim5 files are supported" in str(exc.value)

def test_adapter_rejects_pksim5_with_export_message(tmp_path: Path) -> None:
    from mcp_bridge.adapter.ospsuite import SubprocessOspsuiteAdapter
    from mcp_bridge.adapter.errors import AdapterError
    from mcp_bridge.adapter.interface import AdapterConfig
    
    # Create a dummy .pksim5 file
    model_file = tmp_path / "model.pksim5"
    model_file.write_text("<pksim5 />")
    
    # Configure adapter with this path in search paths
    config = AdapterConfig(model_search_paths=(str(tmp_path),))
    
    # Instantiate adapter with a mocked command runner to avoid starting R
    adapter = SubprocessOspsuiteAdapter(config, command_runner=lambda action, payload: None)
    adapter._initialised = True # Fake init
    
    with pytest.raises(AdapterError) as exc:
        adapter.load_simulation(str(model_file))
        
    assert "Direct loading of .pksim5 files is not supported" in str(exc.value)
    assert "export the simulation as a .pkml file" in str(exc.value)
