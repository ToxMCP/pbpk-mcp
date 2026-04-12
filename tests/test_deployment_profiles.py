from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PACKAGED_COMPOSE = WORKSPACE_ROOT / "docker-compose.celery.yml"
OVERLAY_COMPOSE = WORKSPACE_ROOT / "docker-compose.overlay.yml"
HARDENED_COMPOSE = WORKSPACE_ROOT / "docker-compose.hardened.yml"
S3_AUDIT_SMOKE_COMPOSE = WORKSPACE_ROOT / "docker-compose.s3-audit-smoke.yml"
REFRESH_DOCKERFILE = WORKSPACE_ROOT / "docker" / "runtime-refresh.Dockerfile"
PACKAGED_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_rxode2_stack.sh"
OVERLAY_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_source_overlay_stack.sh"
HARDENED_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_hardened_stack.sh"
S3_AUDIT_SMOKE_DEPLOY = WORKSPACE_ROOT / "scripts" / "deploy_s3_audit_smoke_stack.sh"
S3_AUDIT_SMOKE_SCRIPT = WORKSPACE_ROOT / "scripts" / "s3_audit_smoke.py"
REFRESH_IMAGE_SCRIPT = WORKSPACE_ROOT / "scripts" / "refresh_rxode2_worker_image.sh"
RELEASE_ARTIFACTS_WORKFLOW = WORKSPACE_ROOT / ".github" / "workflows" / "release-artifacts.yml"
MODEL_SMOKE_WORKFLOW = WORKSPACE_ROOT / ".github" / "workflows" / "model-smoke.yml"
WORKER_DOCKERFILE = WORKSPACE_ROOT / "docker" / "rxode2-worker.Dockerfile"
ENV_EXAMPLE = WORKSPACE_ROOT / ".env.example"


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

    def test_packaged_compose_is_default_local_runtime(self) -> None:
        text = PACKAGED_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("ADAPTER_MODEL_PATHS: /app/var", text)
        self.assertIn("ADAPTER_R_PATH: /usr/bin/R", text)
        self.assertIn("ADAPTER_R_HOME: /usr/lib/R", text)
        self.assertIn('AUDIT_ENABLED: "true"', text)
        self.assertIn('ADAPTER_TIMEOUT_MS: "10000"', text)
        self.assertIn('AUTH_ALLOW_ANONYMOUS: "true"', text)
        self.assertIn('AUTH_DEV_SECRET: "pbpk-local-dev-secret"', text)
        self.assertIn("ENVIRONMENT: development", text)
        self.assertIn('127.0.0.1:8000:8000', text)
        self.assertIn('PBPK_ENABLE_SRC_OVERLAY: "false"', text)
        self.assertNotIn("./src:/app/src", text)
        self.assertNotIn("./scripts:/app/scripts", text)
        self.assertNotIn("pbpk_mcp_runtime_src.pth:ro", text)
        self.assertEqual(text.count("./var:/app/var"), 2)

    def test_overlay_compose_enables_workspace_source_overlay(self) -> None:
        text = OVERLAY_COMPOSE.read_text(encoding="utf-8")
        self.assertEqual(text.count('PBPK_ENABLE_SRC_OVERLAY: "true"'), 2)
        self.assertEqual(text.count("./docs:/app/docs"), 2)
        self.assertEqual(text.count("./schemas:/app/schemas"), 2)
        self.assertEqual(text.count("./src:/app/src"), 2)
        self.assertEqual(text.count("./scripts:/app/scripts"), 2)
        self.assertEqual(text.count("./var:/app/var"), 2)
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
        self.assertIn('AUDIT_STORAGE_BACKEND: ${AUDIT_STORAGE_BACKEND:-local}', text)
        self.assertIn('AUDIT_S3_BUCKET: ${AUDIT_S3_BUCKET:-}', text)
        self.assertIn('AUDIT_S3_PREFIX: ${AUDIT_S3_PREFIX:-audit-trail}', text)
        self.assertIn('AUDIT_S3_ENDPOINT_URL: ${AUDIT_S3_ENDPOINT_URL:-}', text)
        self.assertIn('AUDIT_S3_FORCE_PATH_STYLE: ${AUDIT_S3_FORCE_PATH_STYLE:-false}', text)
        self.assertIn('AUDIT_S3_OBJECT_LOCK_MODE: ${AUDIT_S3_OBJECT_LOCK_MODE:-}', text)
        self.assertIn('AUDIT_VERIFY_LOOKBACK_DAYS: ${AUDIT_VERIFY_LOOKBACK_DAYS:-1}', text)
        self.assertIn('${PBPK_BIND_HOST:-127.0.0.1}:${PBPK_BIND_PORT:-8000}:8000', text)

    def test_s3_audit_smoke_overlay_provisions_minio_and_switches_runtime_backend(self) -> None:
        text = S3_AUDIT_SMOKE_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("minio/minio:latest", text)
        self.assertIn("minio/mc:latest", text)
        self.assertIn('AUDIT_STORAGE_BACKEND: s3', text)
        self.assertIn('AUDIT_S3_ENDPOINT_URL: ${AUDIT_S3_ENDPOINT_URL:-http://minio:9000}', text)
        self.assertIn('AUDIT_S3_FORCE_PATH_STYLE: ${AUDIT_S3_FORCE_PATH_STYLE:-true}', text)
        self.assertIn('AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER:-minioadmin}', text)
        self.assertIn('condition: service_completed_successfully', text)
        self.assertIn('PBPK_S3_SMOKE_PORT:-9000', text)

    def test_env_example_defaults_to_packaged_runtime(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn('PBPK_ENABLE_SRC_OVERLAY="false"', text)
        self.assertIn('ADAPTER_MODEL_PATHS="tests/fixtures"', text)
        self.assertIn("removed in v0.5.0", text)
        self.assertIn("Set to true only when you intentionally run the source-overlay maintainer profile.", text)
        self.assertIn("docs/deployment/s3_object_lock_audit.md", text)
        self.assertIn('# AUDIT_S3_ENDPOINT_URL="http://127.0.0.1:9000"', text)
        self.assertIn("# AUDIT_S3_FORCE_PATH_STYLE=true", text)
        self.assertIn('# AWS_ACCESS_KEY_ID="minioadmin"', text)

    def test_s3_audit_smoke_script_checks_signoff_and_s3_verification(self) -> None:
        text = S3_AUDIT_SMOKE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"validate_simulation_request"', text)
        self.assertIn("/review_signoff/history?", text)
        self.assertIn("verify_s3_audit_trail(", text)
        self.assertIn('"signoffStatus": validation_payload["operatorReviewSignoff"]["status"]', text)

    def test_deploy_scripts_wait_for_bound_base_url_without_patch_step(self) -> None:
        packaged_text = PACKAGED_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", packaged_text)
        self.assertIn('wait_for_runtime_ready.py"', packaged_text)
        self.assertIn("--timeout-seconds 600", packaged_text)
        self.assertIn("--per-request-timeout-seconds 30", packaged_text)
        self.assertNotIn("docker-compose.overlay.yml", packaged_text)

        overlay_text = OVERLAY_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", overlay_text)
        self.assertIn("docker-compose.overlay.yml", overlay_text)
        self.assertIn('wait_for_runtime_ready.py"', overlay_text)
        self.assertIn("--timeout-seconds 600", overlay_text)
        self.assertNotIn("apply_rxode2_patch.py", overlay_text)

        text = HARDENED_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", text)
        self.assertIn("docker-compose.hardened.yml", text)
        self.assertIn('PBPK_BIND_HOST:-127.0.0.1', text)
        self.assertIn('PBPK_BIND_PORT:-8000', text)
        self.assertIn('wait_for_runtime_ready.py"', text)
        self.assertIn('--base-url "${base_url}"', text)
        self.assertIn("--timeout-seconds 600", text)
        self.assertNotIn("apply_rxode2_patch.py", text)

        s3_smoke_text = S3_AUDIT_SMOKE_DEPLOY.read_text(encoding="utf-8")
        self.assertIn("docker-compose.celery.yml", s3_smoke_text)
        self.assertIn("docker-compose.s3-audit-smoke.yml", s3_smoke_text)
        self.assertIn('ps -a -q "${service}"', s3_smoke_text)
        self.assertIn("wait_for_service_exit_zero minio-init 90", s3_smoke_text)
        self.assertIn("--timeout-seconds 600", s3_smoke_text)
        self.assertIn('--auth-dev-secret "pbpk-local-dev-secret"', s3_smoke_text)
        self.assertNotIn("docker-compose.hardened.yml", s3_smoke_text)

    def test_refresh_image_helper_reuses_existing_rxode2_image(self) -> None:
        text = REFRESH_IMAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('BASE_IMAGE="${BASE_IMAGE:-pbpk_mcp-worker-rxode2:latest}"', text)
        self.assertIn('IMAGE_TAG="${IMAGE_TAG:-pbpk_mcp-worker-rxode2:latest}"', text)
        self.assertIn("docker/runtime-refresh.Dockerfile", text)
        dockerfile_text = REFRESH_DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("FROM ${BASE_IMAGE}", dockerfile_text)
        self.assertIn("COPY docs /app/docs", dockerfile_text)
        self.assertIn("COPY schemas /app/schemas", dockerfile_text)
        self.assertIn("python -m pip install --no-deps /app", dockerfile_text)

    def test_worker_image_installs_current_package_and_carries_overlay_material(self) -> None:
        text = WORKER_DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("COPY pyproject.toml README.md /app/", text)
        self.assertIn("COPY src /app/src", text)
        self.assertIn("python -m pip install --no-deps /app", text)
        self.assertIn("tomllib.loads(Path('/app/pyproject.toml').read_text(encoding='utf-8'))['project']['version']", text)
        self.assertNotIn("metadata.version('mcp-bridge') == '0.4.0'", text)
        self.assertIn(
            "COPY scripts/runtime_src_overlay.pth /usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth",
            text,
        )
        self.assertIn("COPY scripts/ospsuite_bridge.R /app/scripts/ospsuite_bridge.R", text)
        self.assertIn(
            "COPY reference_models/reference_compound_population_rxode2_model.R /app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R",
            text,
        )
        self.assertNotIn("COPY patches /tmp/pbpk_runtime_source/patches", text)
        self.assertNotIn("install_runtime_patches.py", text)

    def test_runtime_src_overlay_pth_is_disabled_by_default(self) -> None:
        overlay_line = (WORKSPACE_ROOT / "scripts" / "runtime_src_overlay.pth").read_text(encoding="utf-8").strip()
        program = f"""
import json
import os
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
        self.assertNotIn("/app/src", path_prefix)

    def test_runtime_src_overlay_pth_executes_cleanly_and_keeps_app_src_first(self) -> None:
        overlay_line = (WORKSPACE_ROOT / "scripts" / "runtime_src_overlay.pth").read_text(encoding="utf-8").strip()
        program = f"""
import os
import json
import sys
os.environ['PBPK_ENABLE_SRC_OVERLAY'] = 'true'
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
            "python scripts/validate_model_manifests.py --strict --require-explicit-ngra --curated-publication-set",
            text,
        )
        self.assertIn(
            "python scripts/check_distribution_artifacts.py --artifact-dir dist --report-path dist/release-artifact-report.json",
            text,
        )
        self.assertIn("make misuse-prevention-test PY=python", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("dist/*.tar.gz", text)
        self.assertIn("dist/*.whl", text)
        self.assertIn("dist/release-artifact-report.json", text)

    def test_model_smoke_workflow_uses_operator_auth_for_live_smoke_runs(self) -> None:
        text = MODEL_SMOKE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 scripts/public_release_preflight.py", text)
        self.assertIn("--skip-runtime-contract", text)
        self.assertIn(
            "--auth-dev-secret pbpk-local-dev-secret",
            text,
        )
        self.assertIn(
            "var/public_release_preflight_summary.json",
            text,
        )
        self.assertIn(
            "var/release_readiness_summary.json",
            text,
        )
        self.assertIn(
            "var/workspace_model_smoke_rxode2_report.json",
            text,
        )

    def test_runtime_contract_make_target_includes_curated_manifest_gate(self) -> None:
        text = (WORKSPACE_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("runtime-contract-test:", text)
        self.assertIn("misuse-prevention-test:", text)
        self.assertIn("misuse-prevention-live-test:", text)
        self.assertIn("refresh-rxode2-image:", text)
        self.assertIn("s3-audit-smoke:", text)
        self.assertIn("$(MAKE) misuse-prevention-test PY=$(PY)", text)
        self.assertIn(
            "$(PY) scripts/validate_model_manifests.py --strict --require-explicit-ngra --curated-publication-set",
            text,
        )
        self.assertIn("tests/test_workspace_model_smoke_script.py", text)
        self.assertIn("tests/test_release_readiness_script.py", text)
        self.assertIn("tests/test_s3_audit_smoke_script.py", text)
        self.assertIn(
            "$(PY) scripts/workspace_model_smoke.py --include-population --auth-dev-secret pbpk-local-dev-secret",
            text,
        )
        self.assertIn("scripts/s3_audit_smoke.py", text)
        self.assertIn("scripts/refresh_rxode2_worker_image.sh", text)
        self.assertIn("bash scripts/deploy_s3_audit_smoke_stack.sh", text)


if __name__ == "__main__":
    unittest.main()
