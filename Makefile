.DEFAULT_GOAL := help

PY ?= python3
IMAGE_NAME ?= mcp-bridge

.PHONY: help install lint format type test test-e2e test-hpc compliance benchmark benchmark-celery fetch-bench-data parity docs-export sbom check clean build-image refresh-rxode2-image run-image celery-worker runtime-patch-check runtime-contract-test misuse-prevention-test misuse-prevention-live-test workspace-smoke s3-audit-smoke backfill-review-signoff-index public-release-preflight

help:
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ {printf "\033[36m%s\033[0m\t%s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install project in editable mode with dev extras
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e '.[dev]'

lint: ## Run static analysis
	$(PY) -m ruff check src tests

format: ## Format source code
	$(PY) -m black src tests
	$(PY) -m ruff check src tests --fix-only --no-cache

type: ## Run static type checks
	$(PY) -m mypy

test: ## Execute unit tests
	$(PY) -m pytest

test-e2e: fetch-bench-data ## Execute end-to-end regression suite
	$(PY) -m pytest -m e2e --maxfail=1 --durations=10

test-hpc: ## Execute HPC stub regression suite
	$(PY) -m pytest -m hpc_stub --maxfail=1 --durations=10

compliance: ## Run MCP compliance harness
	$(PY) -m pytest -m compliance --maxfail=1

BENCH_PROFILE ?= 0
BENCH_PROFILE_TOP ?= 25

benchmark: ## Run smoke benchmark scenario using in-process ASGI transport
	PYTHONPATH=src $(PY) -m mcp_bridge.benchmarking --scenario smoke --iterations 1 $(if $(filter 1,$(BENCH_PROFILE)),--profile --profile-top $(BENCH_PROFILE_TOP),)

benchmark-celery: ## Run smoke benchmark using Celery inline worker (memory transport)
	JOB_BACKEND=celery $(PY) -m mcp_bridge.benchmarking --scenario smoke --iterations 3 --concurrency 4 --job-backend celery --celery-inline-worker --celery-inline-worker-concurrency 4

fetch-bench-data: ## Ensure reference parity benchmark data is present
	PYTHONPATH=src $(PY) -m mcp_bridge.parity.data

goldset-eval: ## Evaluate literature extraction quality on the gold set
	$(PY) scripts/evaluate_goldset.py --fail-on-threshold

parity: ## Execute the baseline parity validation suite
	PYTHONPATH=src $(PY) -m mcp_bridge.parity.suite --iterations 10

docs-export: ## Regenerate OpenAPI specification and tool JSON schemas
	PYTHONPATH=src $(PY) scripts/export_api_docs.py

sbom: ## Generate CycloneDX-style SBOM for current environment
	$(PY) scripts/generate_sbom.py compliance/sbom.json

retention-report: ## Generate artefact retention & integrity report
	$(PY) scripts/retention_report.py --output var/reports/retention/report.json

check: lint type test ## Run full quality gate

runtime-patch-check: ## Compile the local runtime/deploy helper files used by the live stack
	$(PY) -m py_compile \
		scripts/check_runtime_contract_env.py \
		scripts/check_distribution_artifacts.py \
			scripts/check_release_metadata.py \
			scripts/check_installed_package_contract.py \
			scripts/generate_contract_artifacts.py \
			scripts/backfill_review_signoff_index.py \
			scripts/public_release_preflight.py \
			scripts/release_readiness_check.py \
			scripts/s3_audit_smoke.py \
		scripts/wait_for_runtime_ready.py \
		scripts/workspace_model_smoke.py \
		src/mcp/__init__.py \
		src/mcp/tools/discover_models.py \
		src/mcp/tools/load_simulation.py \
		src/mcp/tools/get_job_status.py \
		src/mcp/tools/get_results.py \
		src/mcp/tools/ingest_external_pbpk_bundle.py \
		src/mcp/tools/export_oecd_report.py \
		src/mcp/tools/run_population_simulation.py \
		src/mcp/tools/run_verification_checks.py \
		src/mcp/tools/validate_model_manifest.py \
		src/mcp/tools/validate_simulation_request.py \
		src/mcp_bridge/adapter/__init__.py \
		src/mcp_bridge/adapter/interface.py \
		src/mcp_bridge/adapter/mock.py \
		src/mcp_bridge/adapter/ospsuite.py \
		src/mcp_bridge/contract/__init__.py \
		src/mcp_bridge/contract/artifacts.py \
		src/mcp_bridge/model_catalog.py \
		src/mcp_bridge/model_manifest.py \
		src/mcp_bridge/pbpk_tools/*.py \
		src/mcp_bridge/routes/resources.py \
		src/mcp_bridge/routes/resources_base.py \
		src/mcp_bridge/tools/registry.py \
		src/mcp_bridge/tools/registry_base.py
		bash -n scripts/build_rxode2_worker_image.sh scripts/refresh_rxode2_worker_image.sh scripts/deploy_rxode2_stack.sh scripts/deploy_source_overlay_stack.sh scripts/deploy_hardened_stack.sh scripts/deploy_s3_audit_smoke_stack.sh

misuse-prevention-test: ## Run the named non-live misuse-prevention regression suite
	$(PY) -m pytest \
		tests/test_calculate_pk_parameters.py \
		tests/test_review_signoff.py \
		tests/test_reviewer_advisory.py \
		tests/test_sensitivity_analysis.py \
		tests/test_trust_surface.py \
		tests/test_model_manifest.py \
		tests/test_external_pbpk_bundle.py \
		tests/test_oecd_bridge.py \
		tests/test_ngra_object_schemas.py \
		tests/test_release_readiness_script.py

misuse-prevention-live-test: ## Run the named live misuse-prevention regression suite against a running local stack
	$(PY) -m pytest -q \
		tests/test_model_discovery_live_stack.py \
		tests/test_oecd_live_stack.py \
		tests/test_runtime_security_live_stack.py

runtime-contract-test: ## Run the local runtime contract tests that do not require the live stack
	$(PY) scripts/check_runtime_contract_env.py
	$(MAKE) misuse-prevention-test PY=$(PY)
	$(PY) scripts/generate_contract_artifacts.py --check
	$(PY) scripts/check_release_metadata.py
	$(PY) scripts/validate_model_manifests.py --strict --require-explicit-ngra --curated-publication-set
	$(PY) scripts/check_distribution_artifacts.py
	$(PY) scripts/check_installed_package_contract.py
	$(PY) -m unittest -v \
		tests/test_calculate_pk_parameters.py \
		tests/test_docs_reference_drift.py \
		tests/test_github_contributor_surface.py \
		tests/test_import_footprint.py \
		tests/test_reviewer_advisory.py \
		tests/test_sensitivity_analysis.py \
		tests/test_capability_matrix.py \
		tests/test_config_contract.py \
		tests/test_deployment_profiles.py \
		tests/test_distribution_artifacts.py \
		tests/test_export_api_docs.py \
		tests/test_ngra_object_schemas.py \
		tests/test_packaged_adapter_namespace.py \
		tests/test_packaged_resource_routes.py \
		tests/test_packaged_mcp_namespace.py \
		tests/test_packaged_tool_registry.py \
		tests/test_mcp_tool_conformance.py \
		tests/test_release_metadata.py \
		tests/test_release_readiness_script.py \
		tests/test_s3_audit_smoke_script.py \
		tests/test_backfill_review_signoff_index_script.py \
		tests/test_public_release_preflight_script.py \
		tests/test_packaged_contract_artifacts.py \
		tests/test_load_simulation_contract.py \
		tests/test_model_manifest.py \
		tests/test_oecd_bridge.py \
		tests/test_external_pbpk_bundle.py \
		tests/test_workspace_model_smoke_script.py
	$(PY) -m pytest tests/unit/test_adapter_interface.py tests/unit/test_subprocess_adapter.py

workspace-smoke: ## Run the live workspace model smoke with rxode2 population enabled
	$(PY) scripts/workspace_model_smoke.py --include-population --auth-dev-secret pbpk-local-dev-secret-32bytes-long

s3-audit-smoke: ## Deploy the packaged stack with a local S3-compatible audit backend and run the smoke check
	bash scripts/deploy_s3_audit_smoke_stack.sh
	$(PY) scripts/s3_audit_smoke.py --auth-dev-secret pbpk-local-dev-secret-32bytes-long

backfill-review-signoff-index: ## Backfill the dedicated review-signoff audit index for a local audit store
	$(PY) scripts/backfill_review_signoff_index.py var/audit

public-release-preflight: ## Run the maintainer pre-public release gate against a running local stack
	$(PY) scripts/public_release_preflight.py --auth-dev-secret pbpk-local-dev-secret-32bytes-long

clean: ## Remove build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build

build-image: ## Build Docker image
	docker build --pull --tag $(IMAGE_NAME) .

refresh-rxode2-image: ## Refresh the packaged rxode2 runtime image from the current workspace without recompiling rxode2
	bash scripts/refresh_rxode2_worker_image.sh

run-image: ## Run Docker image locally
	docker run --rm -p 8000:8000 --env-file .env.example $(IMAGE_NAME)

celery-worker: ## Start a Celery worker (expects JOB_BACKEND=celery and CELERY_* env vars)
	celery -A mcp_bridge.services.celery_app.celery_app worker --loglevel=info
