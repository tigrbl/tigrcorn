# Phase 9F2 logging and exporter closure

This checkpoint executes **Phase 9F2** of the Phase 9 implementation plan.

It closes the remaining pure-operator observability runtime gaps for:

- `--log-config`
- `--statsd-host`
- `--otel-endpoint`

## What changed

### 1. `--log-config` is now a real runtime input

`configure_logging()` now consumes `logging.log_config` as a runtime profile file.

The frozen contract for `--log-config` is:

- accepted file types: JSON, TOML, and Python config files already supported by the repository file loader
- accepted payload shape: either a top-level `logging` mapping or a direct mapping
- accepted keys:
  - `level`
  - `structured`
  - `access_log`
  - `access_log_file`
  - `access_log_format`
  - `error_log_file`
  - `stream`

Frozen precedence:

1. load the `log_config` file
2. then apply explicit CLI logging flags over that file for:
   - `--log-level`
   - `--structured-log`
   - `--access-log-file`
   - `--access-log-format`
   - `--error-log-file`

That closes the old parse-only gap and makes startup fail fast for malformed logging profiles.

### 2. `--statsd-host` now drives a real UDP exporter

The server now starts a live StatsD exporter task when `metrics.statsd_host` is configured.

The frozen contract for `--statsd-host` is:

- syntax: `host:port`
- transport: UDP
- payload: real StatsD datagrams emitted from live metrics snapshots
- lifecycle:
  - exporter starts with the server
  - exporter flushes during shutdown
  - send failures are logged and bounded; they do not abort listener startup

### 3. `--otel-endpoint` now drives a real HTTP exporter

The server now starts a live OTEL exporter task when `metrics.otel_endpoint` is configured.

The frozen contract for `--otel-endpoint` is:

- syntax: `http://...` or `https://...`
- transport: HTTP POST
- content type: `application/json`
- payload family: OTEL-style JSON envelope containing both:
  - `resourceMetrics`
  - `resourceSpans`
- lifecycle spans now include at least:
  - `server.start`
  - `server.shutdown`
- bounded failure behavior:
  - post failures are logged and counted
  - post failures do not abort server startup

### 4. The flag-surface blocker set is smaller now

After this checkpoint, the remaining non-promotion-ready flag/runtime blockers are now only:

- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

## Honest current result

This checkpoint closes only **9F2**.

What is true now:

- the authoritative boundary remains green
- the strict target remains non-green because the preserved HTTP/3 `aioquic` scenarios are still not marked passing
- the flag surface remains non-green, but only because the remaining three hybrid/runtime controls are still open
- the performance target remains non-green
- the composite promotion target remains non-green

So this repository is still **not yet certifiably fully featured** under the stricter promotion target, and it is still **not yet strict-target certifiably fully RFC compliant**.
