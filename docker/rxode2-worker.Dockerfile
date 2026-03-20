ARG BASE_IMAGE=pbpk_mcp-worker:latest

FROM ${BASE_IMAGE} AS layout-check

USER root

RUN mkdir -p \
    /app/scripts \
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

COPY patches /tmp/pbpk_runtime_source/patches
COPY scripts/install_runtime_patches.py /tmp/pbpk_runtime_source/scripts/install_runtime_patches.py
COPY scripts/runtime_patch_manifest.py /tmp/pbpk_runtime_source/scripts/runtime_patch_manifest.py
COPY scripts/ospsuite_bridge.R /tmp/pbpk_runtime_source/scripts/ospsuite_bridge.R
COPY cisplatin_models/cisplatin_population_rxode2_model.R /tmp/pbpk_runtime_source/cisplatin_models/cisplatin_population_rxode2_model.R

RUN python /tmp/pbpk_runtime_source/scripts/install_runtime_patches.py --source-root /tmp/pbpk_runtime_source --target-root / --compile-python --verify-r \
    && Rscript -e "stopifnot(requireNamespace('rxode2', quietly=TRUE)); cat('rxode2 worker image ready\n')"

RUN chown -R mcp:mcp /app/scripts /app/var/models/rxode2

USER mcp
