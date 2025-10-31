# Monitoring & Prometheus Integration

This service now exposes Prometheus-compatible metrics so operators can observe request volume, latency, and saturation directly from the MCP bridge.

## Metrics endpoint

- HTTP `GET /metrics`
- Content type: `text/plain; version=0.0.4`
- Cache control: `no-store`

Example scrape using `curl`:

```shell
curl -s http://localhost:8000/metrics | head
```

## Exported series

| Metric | Type | Labels | Description |
| ------ | ---- | ------ | ----------- |
| `mcp_http_requests_total` | Counter | `method`, `route`, `status_code` | Cumulative HTTP requests processed. |
| `mcp_http_request_duration_seconds` | Histogram | `method`, `route`, `status_code` | Latency distribution with buckets from 5 ms to 60 s. |
| `mcp_http_requests_in_progress` | Gauge | `method`, `route` | In-flight HTTP requests. |
| `mcp_tool_invocations_total` | Counter | `tool`, `status` | Total MCP tool invocations (status = `success`/`error`). |
| `mcp_tool_duration_seconds` | Histogram | `tool`, `status` | Tool execution latency with buckets from 5 ms to 60 s. |
| `mcp_tool_invocations_in_progress` | Gauge | `tool` | Concurrent tool executions. |

Latency buckets allow computation of P50/P95/P99 via PromQL:

```promql
histogram_quantile(0.95, sum(rate(mcp_http_request_duration_seconds_bucket[5m])) by (le))
```

## Prometheus scrape configuration

```yaml
scrape_configs:
  - job_name: mcp-bridge
    metrics_path: /metrics
    scrape_interval: 15s
    static_configs:
      - targets: ["mcp-bridge.local:8000"]
```

## Grafana starter panels

1. Request rate and error rate: `increase(mcp_http_requests_total[5m])` grouped by `status_code`.
2. Latency SLO: `histogram_quantile(0.95, sum(rate(mcp_http_request_duration_seconds_bucket[5m])) by (le, route))`.
3. Saturation: `max(mcp_http_requests_in_progress)` per route.

The starter Grafana dashboard lives at `docs/mcp-bridge/monitoring/grafana-dashboard.json` and includes:

1. HTTP p95 latency time series.
2. Request throughput by method/route.
3. Tool-level p95 latency.
4. Tool error rate over the last 5 minutes.
