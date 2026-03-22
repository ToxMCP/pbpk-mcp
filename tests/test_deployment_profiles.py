from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEV_COMPOSE = WORKSPACE_ROOT / "docker-compose.celery.yml"
HARDENED_COMPOSE = WORKSPACE_ROOT / "docker-compose.hardened.yml"
HARDENED_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_hardened_stack.sh"
PATCH_MANIFEST = WORKSPACE_ROOT / "scripts" / "runtime_patch_manifest.py"
RELEASE_ARTIFACTS_WORKFLOW = WORKSPACE_ROOT / ".github" / "workflows" / "release-artifacts.yml"

spec = importlib.util.spec_from_file_location("pbpk_runtime_patch_manifest_test", PATCH_MANIFEST)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load runtime patch manifest from {PATCH_MANIFEST}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_runtime_patch_manifest_test", module)
spec.loader.exec_module(module)
PATCHES = module.PATCHES
PATCH_TREES = module.PATCH_TREES
WORKER_DOCKERFILE = WORKSPACE_ROOT / "docker" / "rxode2-worker.Dockerfile"


class DeploymentProfileTests(unittest.TestCase):
    def test_development_compose_keeps_explicit_dev_default(self) -> None:
        text = DEV_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('AUTH_ALLOW_ANONYMOUS: "true"', text)
        self.assertIn("ENVIRONMENT: development", text)
        self.assertNotIn("./schemas:/app/schemas:ro", text)
        self.assertNotIn("./docs:/app/docs:ro", text)

    def test_hardened_overlay_disables_anonymous_access_and_requires_auth_env(self) -> None:
        text = HARDENED_COMPOSE.read_text(encoding="utf-8")
        self.assertIn('AUTH_ALLOW_ANONYMOUS: "false"', text)
        self.assertIn("ENVIRONMENT: production", text)
        self.assertIn("${AUTH_ISSUER_URL:?", text)
        self.assertIn("${AUTH_AUDIENCE:?", text)
        self.assertIn("${AUTH_JWKS_URL:?", text)
        self.assertIn('${PBPK_BIND_HOST:-127.0.0.1}:${PBPK_BIND_PORT:-8000}:8000', text)

    def test_hardened_deploy_uses_overlay_and_waits_for_bound_base_url(self) -> None:
        text = HARDENED_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", text)
        self.assertIn("docker-compose.hardened.yml", text)
        self.assertIn('PBPK_BIND_HOST:-127.0.0.1', text)
        self.assertIn('PBPK_BIND_PORT:-8000', text)
        self.assertIn('wait_for_runtime_ready.py" --base-url "${base_url}"', text)

    def test_runtime_patch_manifest_uses_packaged_src_overlay_for_contract_surface(self) -> None:
        file_sources = {patch.source for patch in PATCHES}
        tree_sources = {patch.source for patch in PATCH_TREES}
        expected_trees = {
            "src/mcp",
            "src/mcp_bridge",
        }
        self.assertIn("scripts/runtime_src_overlay.pth", file_sources)
        self.assertEqual(expected_trees, tree_sources)
        self.assertNotIn("docs/architecture/capability_matrix.json", file_sources)
        self.assertNotIn("docs/architecture/contract_manifest.json", file_sources)
        self.assertNotIn("schemas/assessmentContext.v1.json", file_sources)
        self.assertNotIn("schemas/uncertaintySummary.v1.json", file_sources)
        self.assertNotIn("patches/mcp/__init__.py", file_sources)
        self.assertNotIn("patches/mcp/tools/discover_models.py", file_sources)
        self.assertNotIn("patches/mcp/tools/export_oecd_report.py", file_sources)
        self.assertNotIn("patches/mcp/tools/get_job_status.py", file_sources)
        self.assertNotIn("patches/mcp/tools/get_results.py", file_sources)
        self.assertNotIn("patches/mcp/tools/ingest_external_pbpk_bundle.py", file_sources)
        self.assertNotIn("patches/mcp/tools/load_simulation.py", file_sources)
        self.assertNotIn("patches/mcp/tools/run_population_simulation.py", file_sources)
        self.assertNotIn("patches/mcp/tools/run_verification_checks.py", file_sources)
        self.assertNotIn("patches/mcp/tools/validate_simulation_request.py", file_sources)
        self.assertNotIn("patches/mcp/tools/validate_model_manifest.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/adapter/interface.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/adapter/ospsuite.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/model_catalog.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/model_manifest.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/routes/resources.py", file_sources)
        self.assertNotIn("patches/mcp_bridge/tools/registry.py", file_sources)
        self.assertNotIn("src/mcp/__init__.py", file_sources)
        self.assertNotIn("src/mcp_bridge/adapter/interface.py", file_sources)
        self.assertNotIn("src/mcp", file_sources)

    def test_worker_image_carries_src_overlay_material(self) -> None:
        text = WORKER_DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("COPY src /app/src", text)
        self.assertIn("COPY src /tmp/pbpk_runtime_source/src", text)
        self.assertIn(
            "COPY scripts/runtime_src_overlay.pth /tmp/pbpk_runtime_source/scripts/runtime_src_overlay.pth",
            text,
        )

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
