ARG BASE_IMAGE=pbpk_mcp-worker:latest

FROM ${BASE_IMAGE} AS layout-check

USER root

RUN mkdir -p \
    /app/scripts \
    /app/src/mcp \
    /app/src/mcp_bridge \
    /app/var/jobs \
    /app/var/models/rxode2/cisplatin \
    /usr/local/lib/python3.11/site-packages/mcp_bridge/adapter \
    /usr/local/lib/python3.11/site-packages/mcp_bridge/routes \
    /usr/local/lib/python3.11/site-packages/mcp_bridge/tools \
    /usr/local/lib/python3.11/site-packages/mcp_bridge \
    /usr/local/lib/python3.11/site-packages/mcp \
    /usr/local/lib/python3.11/site-packages/mcp/tools

FROM layout-check AS rxode2-worker

ENV DEBIAN_FRONTEND=noninteractive \
    MAKEFLAGS=-j1 \
    R_MAX_VSIZE=6G \
    MALLOC_ARENA_MAX=2

# Keep the one-time image build less memory-hungry than the default toolchain flags.
RUN mkdir -p /root/.R \
    && printf '%s\n' \
        'CFLAGS=-O1 -g0' \
        'CXXFLAGS=-O1 -g0' \
        'CXX11FLAGS=-O1 -g0' \
        'CXX14FLAGS=-O1 -g0' \
        'CXX17FLAGS=-O1 -g0' \
        'FCFLAGS=-O1 -g0' \
        'FFLAGS=-O1 -g0' \
        'MAKE=make -j1' \
        > /root/.R/Makevars

RUN Rscript -e "options(Ncpus=1L); install.packages('rxode2', repos='https://cloud.r-project.org')"

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY scripts/runtime_src_overlay.pth /usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth
COPY scripts/ospsuite_bridge.R /app/scripts/ospsuite_bridge.R
COPY cisplatin_models/cisplatin_population_rxode2_model.R /app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R

RUN python -m pip install --no-deps /app \
    && python -c "import importlib.metadata as metadata; assert metadata.version('mcp-bridge') == '0.4.0'" \
    && python -c "import os, sys; from pathlib import Path; statement = Path('/usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth').read_text(encoding='utf-8').strip(); original = list(sys.path); sys.path[:] = ['keep-a', '/app/src', 'keep-b']; os.environ.pop('PBPK_ENABLE_SRC_OVERLAY', None); exec(statement, {}); assert '/app/src' not in sys.path; sys.path[:] = ['keep-a', '/app/src', 'keep-b']; os.environ['PBPK_ENABLE_SRC_OVERLAY'] = 'true'; exec(statement, {}); assert sys.path[0] == '/app/src'; assert sys.path.count('/app/src') == 1; sys.path[:] = original" \
    && Rscript -e "invisible(parse(file='/app/scripts/ospsuite_bridge.R')); invisible(parse(file='/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R')); stopifnot(requireNamespace('rxode2', quietly=TRUE)); cat('rxode2 worker image ready\n')"

RUN chown -R mcp:mcp /app/scripts /app/var

USER mcp
