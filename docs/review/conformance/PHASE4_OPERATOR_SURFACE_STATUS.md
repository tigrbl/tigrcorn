# Phase 4 operator-surface status

This checkpoint lands the Phase 4 operator-surface implementation.

## What is now present in-tree

### Workers / supervision

- parent-side prebinding for TCP, UDP, and Unix listeners
- inherited file-descriptor support in listener implementations
- a real `ProcessWorker` abstraction with health snapshots, restart, and stop semantics
- a real `WorkerSupervisor` with replacement and unhealthy-worker reporting
- a `ServerSupervisor` that prebinds listeners, starts worker processes, polls worker health, and replaces dead workers
- request-budget-driven worker recycle support via `limit_max_requests` and `max_requests_jitter`

### Reload

- stdlib polling reloader in `src/tigrcorn/server/reloader.py`
- import-root polling with include/exclude globs
- child restart semantics without adding a runtime dependency
- reload / workers constraints enforced in config validation

### Reverse proxy correctness

- trusted proxy parsing in `src/tigrcorn/utils/proxy.py`
- `Forwarded` and `X-Forwarded-*` normalization
- `root_path` injection and prefix stripping in HTTP and WebSocket scopes
- forwarded client/server/scheme propagation into ASGI scope building

### Logging / observability

- structured JSON logging support
- file sinks for access/error logs
- configurable access-log formatting
- richer metrics counters and exporter renderers
- Prometheus-style metrics endpoint when `metrics.enabled` and `metrics.bind` are set
- StatsD-style rendering helpers and span sampling primitives

### Public runtime controls now wired

- keep-alive timeout
- read timeout
- write timeout
- graceful shutdown timeout
- backlog
- max header size
- WebSocket max message size
- scheduler quotas
- stream limits for HTTP/2 and QUIC transport parameters
- idle timeout
- QUIC datagram and QUIC idle settings

## Honest status

- the authoritative canonical boundary remains green and release-passing
- this checkpoint broadens the non-RFC operator surface and makes it real
- the stricter all-surfaces-independent RFC overlay still depends primarily on preserved independent artifacts and broader flow-control / intermediary evidence

## Validation snapshot for this checkpoint

Focused validation performed for this checkpoint:

- `tests/test_phase4_operator_surface.py`
- `tests/test_phase2_cli_config_surface.py`
- `tests/test_observability_workers.py`
- `tests/test_cli_and_asgi3.py`
- `tests/test_config_matrix.py`
- `tests/test_release_gates.py`
- `tests/test_phase3_strict_rfc_surface.py`
- `tests/test_server_http1.py`
- `tests/test_server_http2.py`
- `tests/test_server_websocket.py`
- `tests/test_server_unix.py`
- `tests/test_public_api_cli_mtls_surface.py`

Checkpoint result:

- focused operator/config/runtime suite: `28 passed`
- canonical release-gate / strict-RFC suite: `9 passed`
- server/runtime smoke suite: `9 passed`

Total targeted validation: `46 passed`
