FROM ghcr.io/astral-sh/uv:0.12.21 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY . /app
RUN uv sync --frozen --no-dev --no-editable && useradd --uid 10001 --create-home transport
ENV PATH="/app/.venv/bin:$PATH"
USER 10001
EXPOSE 8000
CMD ["pbpk-mcp-sdk2-http", "--host", "0.0.0.0", "--port", "8000"]
