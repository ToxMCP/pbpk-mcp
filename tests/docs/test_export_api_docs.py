"""Tests for the OpenAPI and schema export helper."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def test_export_api_docs(tmp_path) -> None:
    contracts_dir = tmp_path / "contracts"
    schemas_dir = tmp_path / "schemas"

    cmd = [
        sys.executable,
        "scripts/export_api_docs.py",
        "--contracts-dir",
        str(contracts_dir),
        "--schemas-dir",
        str(schemas_dir),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr

    openapi_path = contracts_dir / "openapi.json"
    assert openapi_path.exists()
    with openapi_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    assert "paths" in schema and "/cancel_job" in schema["paths"]

    cancel_request_schema = schemas_dir / "cancel_job-request.json"
    assert cancel_request_schema.exists()
