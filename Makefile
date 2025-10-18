.DEFAULT_GOAL := help

PY ?= python3
IMAGE_NAME ?= mcp-bridge

.PHONY: help install lint format type test check clean build-image run-image

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

benchmark: ## Run smoke benchmark scenario using in-process ASGI transport
	PYTHONPATH=src $(PY) -m mcp_bridge.benchmarking --scenario smoke --iterations 1

check: lint type test ## Run full quality gate

clean: ## Remove build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build

build-image: ## Build Docker image
	docker build --pull --tag $(IMAGE_NAME) .

run-image: ## Run Docker image locally
	docker run --rm -p 8000:8000 --env-file .env.example $(IMAGE_NAME)
