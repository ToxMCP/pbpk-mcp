# syntax=docker/dockerfile:1.6

ARG PYTHON_VERSION=3.11-slim
ARG OSPSUITE_VERSION=12.3.2

FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:${PYTHON_VERSION} AS runtime
ARG OSPSUITE_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    OSPSUITE_VERSION=${OSPSUITE_VERSION}

# Install system dependencies and R
RUN apt-get update && apt-get install --yes --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    apt-transport-https \
    # R dependencies
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    libicu-dev \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

# Install .NET runtime required by ospsuite (amd64 only)
RUN ARCH="$(dpkg --print-architecture)"; \
    if [ "$ARCH" = "amd64" ]; then \
        wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
        dpkg -i packages-microsoft-prod.deb && \
        rm packages-microsoft-prod.deb && \
        apt-get update && \
        apt-get install --yes --no-install-recommends dotnet-runtime-8.0 && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Skipping .NET runtime installation for architecture ${ARCH}."; \
    fi

# Install the ospsuite R package when supported
RUN ARCH="$(dpkg --print-architecture)"; \
    if [ "$ARCH" = "amd64" ]; then \
        R -q -e "options(repos = c(CRAN='https://cloud.r-project.org')); install.packages('remotes', repos='https://cloud.r-project.org');" && \
        R -q -e "remotes::install_github('Open-Systems-Pharmacology/OSPSuite-R', ref = sprintf('v%s', Sys.getenv('OSPSUITE_VERSION')), upgrade = 'never');" && \
        R -q -e "cat('Installed ospsuite version:', as.character(packageVersion('ospsuite')), '\n')"; \
    else \
        echo "ospsuite installation skipped for architecture ${ARCH}. Set ADAPTER_BACKEND=inmemory to use the mock adapter."; \
    fi

# Set default R environment variables
ENV R_PATH=/usr/bin/R \
    R_HOME=/usr/lib/R \
    OSPSUITE_LIBS=/usr/local/lib/R/site-library \
    ADAPTER_TIMEOUT_SECONDS=10

RUN groupadd --system mcp \
    && useradd --system --gid mcp --create-home mcp

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

COPY src ./src

ENV PATH="/usr/local/bin:$PATH"

USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["/usr/local/bin/python", "-m", "uvicorn", "mcp_bridge.main:app", "--host", "0.0.0.0", "--port", "8000"]
