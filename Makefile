.DEFAULT_GOAL := help

PY ?= python3
IMAGE_NAME ?= mcp-bridge

.PHONY: help install lint format type test test-e2e test-hpc compliance benchmark benchmark-celery fetch-bench-data parity docs-export sbom check clean build-image run-image celery-worker runtime-patch-check runtime-contract-test workspace-smoke

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
	$(PY) -m mypy src

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

runtime-patch-check: ## Compile the patch-first runtime files used by the live stack
	$(PY) -m py_compile \
		scripts/check_runtime_contract_env.py \
		scripts/check_distribution_artifacts.py \
		scripts/check_release_metadata.py \
		scripts/check_installed_package_contract.py \
		scripts/generate_contract_artifacts.py \
		scripts/runtime_patch_manifest.py \
		scripts/install_runtime_patches.py \
		scripts/apply_rxode2_patch.py \
		scripts/release_readiness_check.py \
		scripts/wait_for_runtime_ready.py \
		scripts/workspace_model_smoke.py \
		patches/mcp/tools/load_simulation.py \
		patches/mcp/tools/get_job_status.py \
		patches/mcp/tools/get_results.py \
		patches/mcp/tools/discover_models.py \
		patches/mcp/tools/validate_model_manifest.py \
		patches/mcp/tools/validate_simulation_request.py \
		patches/mcp/tools/export_oecd_report.py \
		patches/mcp/tools/run_population_simulation.py \
		src/mcp_bridge/contract/__init__.py \
		src/mcp_bridge/contract/artifacts.py \
		patches/mcp_bridge/model_catalog.py \
		patches/mcp_bridge/model_manifest.py \
		patches/mcp_bridge/routes/resources.py \
		patches/mcp_bridge/tools/registry.py

runtime-contract-test: ## Run the patch-first runtime contract tests that do not require the live stack
	$(PY) scripts/check_runtime_contract_env.py
	$(PY) scripts/generate_contract_artifacts.py --check
	$(PY) scripts/check_release_metadata.py
	$(PY) scripts/check_distribution_artifacts.py
	$(PY) scripts/check_installed_package_contract.py
	$(PY) -m unittest -v \
		tests/test_capability_matrix.py \
		tests/test_deployment_profiles.py \
		tests/test_distribution_artifacts.py \
		tests/test_ngra_object_schemas.py \
		tests/test_release_metadata.py \
		tests/test_packaged_contract_artifacts.py \
		tests/test_load_simulation_contract.py \
		tests/test_model_manifest.py \
		tests/test_oecd_bridge.py \
		tests/test_external_pbpk_bundle.py

workspace-smoke: ## Run the live workspace model smoke with rxode2 population enabled
	$(PY) scripts/workspace_model_smoke.py --include-population

clean: ## Remove build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build

build-image: ## Build Docker image
	docker build --pull --tag $(IMAGE_NAME) .

run-image: ## Run Docker image locally
	docker run --rm -p 8000:8000 --env-file .env.example $(IMAGE_NAME)

celery-worker: ## Start a Celery worker (expects JOB_BACKEND=celery and CELERY_* env vars)
	celery -A mcp_bridge.services.celery_app.celery_app worker --loglevel=info
