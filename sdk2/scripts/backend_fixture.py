"""Offline transport fixture: the real released backend with its InMemoryAdapter.

No R/ospsuite qualification is claimed. The production backend modules are neither
copied nor patched; the fixture configures development JWTs and isolated storage.
"""

import argparse
import os
from pathlib import Path

import uvicorn
from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig

SECRET = "pbpk-sdk2-offline-fixture-secret-32bytes!!"

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--workspace", type=Path, required=True)
args = parser.parse_args()
os.environ["ADAPTER_MODEL_PATHS"] = str(args.workspace)
config = AppConfig.model_validate(
    {
        "environment": "development",
        "adapter_backend": "inmemory",
        "auth_dev_secret": SECRET,
        "auth_allow_anonymous": False,
        "auth_rate_limit_per_minute": 10000,
        "audit_enabled": False,
        "adapter_model_paths": [str(args.workspace)],
        "population_storage_path": str(args.workspace / "population"),
        "snapshot_storage_path": str(args.workspace / "snapshots"),
        "job_registry_path": str(args.workspace / f"jobs-{args.port}.json"),
    }
)
uvicorn.run(create_app(config), host="127.0.0.1", port=args.port, log_level="error")
