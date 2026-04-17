ARG BASE_IMAGE=pbpk_mcp-worker-rxode2:latest

FROM ${BASE_IMAGE}

USER root

COPY pyproject.toml README.md MANIFEST.in /app/
COPY CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md CHANGELOG.md /app/
COPY src /app/src
COPY scripts /app/scripts
COPY docs /app/docs
COPY schemas /app/schemas
COPY benchmarks /app/benchmarks
COPY reference_models /app/reference_models
COPY scripts/runtime_src_overlay.pth /usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth
COPY scripts/ospsuite_bridge.R /app/scripts/ospsuite_bridge.R
COPY reference_models/reference_compound_population_rxode2_model.R /app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R

RUN python -m pip install --no-deps /app \
    && python -c "import importlib.metadata as metadata, tomllib; from pathlib import Path; expected = tomllib.loads(Path('/app/pyproject.toml').read_text(encoding='utf-8'))['project']['version']; assert metadata.version('mcp-bridge') == expected"

USER mcp
