from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEV_COMPOSE = WORKSPACE_ROOT / "docker-compose.celery.yml"
HARDENED_COMPOSE = WORKSPACE_ROOT / "docker-compose.hardened.yml"
DEV_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_rxode2_stack.sh"
HARDENED_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_hardened_stack.sh"
RELEASE_ARTIFACTS_WORKFLOW = WORKSPACE_ROOT / ".github" / "workflows" / "release-artifacts.yml"
WORKER_DOCKERFILE = WORKSPACE_ROOT / "docker" / "rxode2-worker.Dockerfile"


class DeploymentProfileTests(unittest.TestCase):
    def test_no_tracked_patch_implementation_files_remain(self) -> None:
        patch_root = WORKSPACE_ROOT / "patches"
        if not patch_root.exists():
            return
        remaining = [
            path.relative_to(WORKSPACE_ROOT).as_posix()
            for path in patch_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        ]
        self.assertEqual(remaining, [])

    def test_development_compose_keeps_explicit_dev_default(self) -> None:
        text = DEV_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('AUTH_ALLOW_ANONYMOUS: "true"', text)
        self.assertIn("ENVIRONMENT: development", text)
        self.assertNotIn("./schemas:/app/schemas:ro", text)
        self.assertNotIn("./docs:/app/docs:ro", text)
        self.assertEqual(
            text.count(
                "./scripts/runtime_src_overlay.pth:/usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth:ro"
            ),
            2,
        )

    def test_hardened_overlay_disables_anonymous_access_and_requires_auth_env(self) -> None:
        text = HARDENED_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('AUTH_ALLOW_ANONYMOUS: "false"', text)
        self.assertIn("ENVIRONMENT: production", text)
        self.assertIn("${AUTH_ISSUER_URL:?", text)
        self.assertIn("${AUTH_AUDIENCE:?", text)
        self.assertIn("${AUTH_JWKS_URL:?", text)
        self.assertIn('${PBPK_BIND_HOST:-127.0.0.1}:${PBPK_BIND_PORT:-8000}:8000', text)

    def test_deploy_scripts_wait_for_bound_base_url_without_patch_step(self) -> None:
        dev_text = DEV_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", dev_text)
        self.assertIn('wait_for_runtime_ready.py"', dev_text)
        self.assertNotIn("apply_rxode2_patch.py", dev_text)

        text = HARDENED_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", text)
        self.assertIn("docker-compose.hardened.yml", text)
        self.assertIn('PBPK_BIND_HOST:-127.0.0.1', text)
        self.assertIn('PBPK_BIND_PORT:-8000', text)
        self.assertIn('wait_for_runtime_ready.py" --base-url "${base_url}"', text)
        self.assertNotIn("apply_rxode2_patch.py", text)

    def test_worker_image_carries_src_overlay_material(self) -> None:
        text = WORKER_DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("COPY src /app/src", text)
        self.assertIn(
            "COPY scripts/runtime_src_overlay.pth /usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth",
            text,
        )
        self.assertIn("COPY scripts/ospsuite_bridge.R /app/scripts/ospsuite_bridge.R", text)
        self.assertIn(
            "COPY cisplatin_models/cisplatin_population_rxode2_model.R /app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
            text,
        )
        self.assertNotIn("COPY patches /tmp/pbpk_runtime_source/patches", text)
        self.assertNotIn("install_runtime_patches.py", text)

    def test_runtime_src_overlay_pth_executes_cleanly_and_keeps_app_src_first(self) -> None:
        overlay_line = (WORKSPACE_ROOT / "scripts" / "runtime_src_overlay.pth").read_text(encoding="utf-8").strip()
        program = f"""
import json
import sys
sys.path[:] = ['keep-a', '/app/src', 'keep-b']
exec({overlay_line!r})
print(json.dumps(sys.path[:3]))
"""
        completed = subprocess.run(
            [sys.executable, "-S", "-c", program],
            check=True,
            capture_output=True,
            text=True,
        )
        path_prefix = json.loads(completed.stdout.strip())
        self.assertEqual(path_prefix[0], "/app/src")
        self.assertEqual(path_prefix.count("/app/src"), 1)

    def test_release_artifacts_workflow_validates_and_uploads_distribution_boundary(self) -> None:
        text = RELEASE_ARTIFACTS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('tags: ["v*"]', text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("python scripts/check_runtime_contract_env.py", text)
        self.assertIn("python scripts/generate_contract_artifacts.py --check", text)
        self.assertIn("python scripts/check_release_metadata.py", text)
        self.assertIn(
            "python scripts/check_distribution_artifacts.py --artifact-dir dist --report-path dist/release-artifact-report.json",
            text,
        )
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("dist/*.tar.gz", text)
        self.assertIn("dist/*.whl", text)
        self.assertIn("dist/release-artifact-report.json", text)


if __name__ == "__main__":
    unittest.main()
