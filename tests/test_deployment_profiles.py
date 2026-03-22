from __future__ import annotations

import importlib.util
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

    def test_runtime_patch_manifest_carries_public_contract_artifacts(self) -> None:
        manifest_sources = {patch.source for patch in PATCHES}
        expected = {
            "docs/architecture/capability_matrix.json",
            "docs/architecture/contract_manifest.json",
            "src/mcp/tools/discover_models.py",
            "src/mcp/tools/export_oecd_report.py",
            "src/mcp/tools/get_job_status.py",
            "src/mcp/tools/get_results.py",
            "src/mcp/tools/ingest_external_pbpk_bundle.py",
            "src/mcp/tools/load_simulation.py",
            "src/mcp/tools/run_verification_checks.py",
            "src/mcp/tools/run_population_simulation.py",
            "src/mcp/tools/validate_simulation_request.py",
            "src/mcp/tools/validate_model_manifest.py",
            "src/mcp_bridge/model_catalog.py",
            "src/mcp_bridge/model_manifest.py",
            "src/mcp_bridge/routes/resources_base.py",
            "src/mcp_bridge/tools/registry_base.py",
            "schemas/assessmentContext.v1.json",
            "schemas/berInputBundle.v1.json",
            "schemas/internalExposureEstimate.v1.json",
            "schemas/pbpkQualificationSummary.v1.json",
            "schemas/pointOfDepartureReference.v1.json",
            "schemas/uncertaintyHandoff.v1.json",
            "schemas/uncertaintyRegisterReference.v1.json",
            "schemas/uncertaintySummary.v1.json",
            "schemas/examples/assessmentContext.v1.example.json",
            "schemas/examples/berInputBundle.v1.example.json",
            "schemas/examples/internalExposureEstimate.v1.example.json",
            "schemas/examples/pbpkQualificationSummary.v1.example.json",
            "schemas/examples/pointOfDepartureReference.v1.example.json",
            "schemas/examples/uncertaintyHandoff.v1.example.json",
            "schemas/examples/uncertaintyRegisterReference.v1.example.json",
            "schemas/examples/uncertaintySummary.v1.example.json",
        }
        self.assertTrue(expected.issubset(manifest_sources))
        self.assertNotIn("patches/mcp/tools/discover_models.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/export_oecd_report.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/get_job_status.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/get_results.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/ingest_external_pbpk_bundle.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/load_simulation.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/run_population_simulation.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/run_verification_checks.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/validate_simulation_request.py", manifest_sources)
        self.assertNotIn("patches/mcp/tools/validate_model_manifest.py", manifest_sources)
        self.assertNotIn("patches/mcp_bridge/model_catalog.py", manifest_sources)
        self.assertNotIn("patches/mcp_bridge/model_manifest.py", manifest_sources)

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
