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

COPY patches/mcp/__init__.py /usr/local/lib/python3.11/site-packages/mcp/__init__.py
COPY patches/mcp_bridge/adapter/ospsuite.py /usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/ospsuite.py
COPY patches/mcp_bridge/model_catalog.py /usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py
COPY patches/mcp_bridge/model_manifest.py /usr/local/lib/python3.11/site-packages/mcp_bridge/model_manifest.py
COPY patches/mcp_bridge/routes/resources.py /usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources.py
COPY patches/mcp_bridge/tools/registry.py /usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry.py
COPY patches/mcp/tools/load_simulation.py /usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py
COPY patches/mcp/tools/get_job_status.py /usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py
COPY patches/mcp/tools/discover_models.py /usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py
COPY patches/mcp/tools/export_oecd_report.py /usr/local/lib/python3.11/site-packages/mcp/tools/export_oecd_report.py
COPY patches/mcp/tools/validate_model_manifest.py /usr/local/lib/python3.11/site-packages/mcp/tools/validate_model_manifest.py
COPY patches/mcp/tools/get_results.py /usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py
COPY patches/mcp/tools/validate_simulation_request.py /usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py
COPY scripts/ospsuite_bridge.R /app/scripts/ospsuite_bridge.R
COPY cisplatin_models/cisplatin_population_rxode2_model.R /app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R

RUN python -c "import py_compile; files = ['/usr/local/lib/python3.11/site-packages/mcp/__init__.py', '/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/ospsuite.py', '/usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py', '/usr/local/lib/python3.11/site-packages/mcp_bridge/model_manifest.py', '/usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources.py', '/usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/export_oecd_report.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/validate_model_manifest.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py', '/usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py']; [py_compile.compile(path, doraise=True) for path in files]" \
    && Rscript -e "stopifnot(requireNamespace('rxode2', quietly=TRUE)); invisible(parse(file='/app/scripts/ospsuite_bridge.R')); invisible(parse(file='/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R')); cat('rxode2 worker image ready\n')"

RUN chown -R mcp:mcp /app/scripts /app/var/models/rxode2

USER mcp
