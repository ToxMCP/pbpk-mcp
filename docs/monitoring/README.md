# MCP Bridge Monitoring

This directory contains ready-to-use assets for instrumenting the MCP Bridge
with Prometheus and visualising the exported metrics in Grafana.

## Prerequisites

- MCP Bridge running with the `/metrics` endpoint exposed (enabled by default).
- Prometheus scraping the bridge instance (example scrape config below).
- Grafana instance with the Prometheus data source configured.

### Prometheus scrape configuration

```yaml
scrape_configs:
  - job_name: mcp-bridge
    metrics_path: /metrics
    scrape_interval: 15s
    static_configs:
      - targets:
          - mcp-bridge.local:8000
```

Adjust the target host/port to match your deployment.

## Default Grafana Dashboard

- `grafana-mcp-bridge-dashboard.json` – opinionated dashboard covering:
  - HTTP request volume and P95 latency per route.
  - MCP tool invocation latency, throughput, and outcomes.
  - In-flight request gauge.
  - 4xx/5xx error rates.

### Import steps

1. Open Grafana ➜ *Dashboards* ➜ *New* ➜ *Import*.
2. Paste the JSON file contents or upload the file directly.
3. Select the Prometheus data source used to scrape the bridge.
4. Save the dashboard; tailor panels or thresholds as required.

## Extending Metrics

The bridge already exports:

- `mcp_http_request_duration_seconds_*` / `mcp_http_requests_total` /
  `mcp_http_requests_in_progress`.
- `mcp_tool_duration_seconds_*` / `mcp_tool_invocations_total`.

To instrument additional subsystems (e.g., Celery queue depth, adapter metrics),
use the `prometheus_client` primitives directly within the relevant modules and
add panels to the dashboard referencing those series.

## Benchmarks & Alerts

- Bench harness outputs (cold/steady/stress scenarios) can feed Grafana as
  additional data sources for historical comparison.
- Suggested alerts:
  - HTTP P95 latency above target for >5 minutes.
  - Tool failure rate >5% over a 10-minute window.
  - Request concurrency approaching service capacity.

Feel free to version dashboards in this directory as you iterate on production
observability requirements.
