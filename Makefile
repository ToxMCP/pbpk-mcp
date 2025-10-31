.DEFAULT_GOAL := help

PY ?= python3
IMAGE_NAME ?= mcp-bridge

.PHONY: help install lint format type test test-e2e test-hpc compliance benchmark benchmark-celery fetch-bench-data parity docs-export sbom check clean build-image run-image celery-worker

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

clean: ## Remove build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build

build-image: ## Build Docker image
	docker build --pull --tag $(IMAGE_NAME) .

run-image: ## Run Docker image locally
	docker run --rm -p 8000:8000 --env-file .env.example $(IMAGE_NAME)

celery-worker: ## Start a Celery worker (expects JOB_BACKEND=celery and CELERY_* env vars)
	celery -A mcp_bridge.services.celery_app.celery_app worker --loglevel=info
