> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current Repository State — Phase 1 Surface Parity Checkpoint

## Scope of this checkpoint

This checkpoint is a **Phase 1 delivery** focused on:

- surface parity and configuration foundation
- response header policy normalization
- config-source maturity
- runtime/supervisor/operator-surface hardening
- host allowlist and embedded/server-adjacent support

This checkpoint **does not certify** the repository as fully complete against the broader expansion program that includes full RFC closure, cache/freshness policy, integrity/trust, gateway/enforcement features, or all future Phase 2–4 work.

## Current certification statement

- **Current internal promotion target**: green in this checkpoint.
- **Certifiably fully featured against the expanded program**: **no**.
- **Certifiably fully RFC compliant against the expanded program**: **no**.

The repository can truthfully claim that this checkpoint closes a substantial set of **Phase 1 public-surface and configuration gaps**, and that the focused validation bundle listed below passed.

## Implemented in this checkpoint

### CLI and configuration surface

Implemented or expanded:

- `--env-file`
- `--runtime auto|asyncio|uvloop`
- `--worker-healthcheck-timeout`
- `--user`
- `--group`
- `--umask`
- `--date-header` / `--no-date-header`
- `--header` (repeatable default response header injection)
- `--server-name` (host / authority allowlist)
- `--use-colors` / `--no-use-colors`

Config loading expanded to support:

- JSON
- TOML
- YAML / YML when a YAML loader is available in the runtime
- Python config file
- `module:<module>` config source
- `object:<module>:<name>` config source
- mapping / dict / dataclass / object ingestion
- env-file bootstrap with precedence:
  `CLI > env > env-file > file > defaults`

### Runtime and process surface

Implemented or expanded:

- worker startup healthcheck timeout supervision
- runtime-aware sync entrypoints (`auto`, `asyncio`, `uvloop`)
- unix socket ownership controls (`user`, `group`, `umask`)
- colorized logging toggle
- reload hook execution surface

### Response header policy normalization

Implemented across HTTP response writers / handlers:

- default response header injection
- date header policy
- server header policy normalization
- H1 / H2 / H3 response header policy application
- WebSocket HTTP handshake / denial path header policy application

### Host / authority allowlist

Implemented:

- HTTP/1.1 host allowlist checks
- HTTP/2 authority allowlist checks for normal requests and H2 WebSocket extended CONNECT
- HTTP/3 authority allowlist checks for normal requests and H3 WebSocket CONNECT
- wildcard and host:port allowlist matching helpers

### Embedded lifecycle hooks

Implemented:

- startup hooks
- shutdown hooks
- reload hooks

### Static files

Implemented:

- `tigrcorn.static.StaticFilesApp`
- safe path normalization
- GET / HEAD
- content-type / content-length / last-modified response metadata
- traversal blocking

## Known partials and remaining gaps

These are still partial or intentionally deferred in this checkpoint:

- The supported public runtime surface is now limited to `auto`, `asyncio`, and `uvloop`; `trio` has been deliberately descoped until it can be wired end to end.
- Static file delivery is a **Phase 1 foundation**, not the full Phase 2 semantic package. It does **not** yet claim complete ETag / conditional / range conformance.
- This checkpoint does **not** claim full RFC 9110 / 7232 / 7233 / 9112 / 9113 / 9114 / 9000 / 9001 / 9204 closure beyond what the repository already documented before this Phase 1 work.
- This checkpoint does **not** expand into cache/freshness policy, integrity/trust, or gateway/enforcement product boundaries.

## Main modules touched

Primary modified or added modules:

- `src/tigrcorn/cli.py`
- `src/tigrcorn/api.py`
- `src/tigrcorn/constants.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/env.py`
- `src/tigrcorn/config/files.py`
- `src/tigrcorn/config/load.py`
- `src/tigrcorn/config/normalize.py`
- `src/tigrcorn/config/validate.py`
- `src/tigrcorn/utils/headers.py`
- `src/tigrcorn/utils/authority.py`
- `src/tigrcorn/server/bootstrap.py`
- `src/tigrcorn/server/hooks.py`
- `src/tigrcorn/server/reloader.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/server/supervisor.py`
- `src/tigrcorn/workers/process.py`
- `src/tigrcorn/observability/logging.py`
- `src/tigrcorn/protocols/http1/serializer.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`
- `src/tigrcorn/protocols/websocket/handshake.py`
- `src/tigrcorn/protocols/websocket/handler.py`
- `src/tigrcorn/asgi/send.py`
- `src/tigrcorn/static.py`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/flag_contracts.json`
- `docs/review/conformance/flag_covering_array.json`
- `tests/test_phase1_surface_parity_checkpoint.py`

## Focused validation completed in this checkpoint

The following focused validation bundle passed:

- `tests/test_phase1_surface_parity_checkpoint.py`
- `tests/test_phase2_cli_config_surface.py`
- `tests/test_phase4_operator_surface.py`
- `tests/test_server_http1.py`
- `tests/test_server_unix.py`
- `tests/test_server_websocket.py`
- `tests/test_config_matrix.py`
- `tests/test_phase9f2_logging_exporter_closure.py`

Observed result for that bundle:

- **41 passed**
- **0 failed**

Additional validation completed:

- `python -m compileall -q src/tigrcorn`
- internal promotion-target evaluation returned green for the repository’s current configured target

## Practical interpretation

This zip is a strong **Phase 1 checkpoint** with a current-state report, public-surface closure work, focused tests, and a packageable repository snapshot.

It should be treated as:

- a valid checkpoint for continued delivery
- a substantially improved operator/configuration surface
- **not** the final word on the broader “fully featured / fully RFC compliant” expansion program
