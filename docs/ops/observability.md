# Observability Operator Guide

This file is generated from the package-owned Phase 6 observability metadata and the public CLI parser.

## Export adapters

| Flag | Config path | Schema version | Help | Accepted values | Failure behavior |
|---|---|---|---|---|---|
| `--statsd-host` | `metrics.statsd_host` | `statsd-dogstatsd-v1` | Export metrics to StatsD or DogStatsD using host:port, statsd://host:port, or dogstatsd://host:port | `host:port`, `statsd://host:port`, `dogstatsd://host:port` | Send failures are bounded, counted, and do not abort server startup or shutdown. |
| `--otel-endpoint` | `metrics.otel_endpoint` | `otlp-http-json-v1` | Export metrics and spans to the package-owned OTLP-style HTTP collector endpoint | `http://collector/v1/telemetry`, `https://collector/v1/telemetry` | POST failures are bounded, counted, and preserve buffered spans for retry on the next cycle. |

## Frozen behavior

- Metrics are package-owned names exported from one in-process snapshot model; exporter adapters do not rename counters.
- `--statsd-host` accepts plain `host:port`, `statsd://host:port`, or `dogstatsd://host:port`.
- `--otel-endpoint` accepts `http://` and `https://` collector URLs and emits the declared OTLP-style JSON envelope.
- qlog output is explicitly experimental, versioned, and redacted; it is not a stable compatibility target.
