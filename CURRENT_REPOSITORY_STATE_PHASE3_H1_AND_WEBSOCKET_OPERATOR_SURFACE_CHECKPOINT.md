# Phase 3 HTTP/1.1 and WebSocket operator-surface checkpoint

This checkpoint completes the missing HTTP/1.1 and WebSocket operator-grade controls inside the current T/P/A/D/R boundary.

What landed:

- public CLI/config/env controls for `--http1-max-incomplete-event-size`, `--http1-buffer-size`, `--http1-header-read-timeout`, `--http1-keep-alive`, `--no-http1-keep-alive`, and `--websocket-max-queue`
- a package-owned HTTP/1.1 request-head incomplete-event cap enforced during incremental request-head reads
- HTTP/1.1 request-body chunk sizing aligned to the protocol-specific `--http1-buffer-size` control while preserving the generic body and header budgets
- an HTTP/1.1-specific request-head read timeout that tightens the generic read/keep-alive timeout during header parsing without broadening the package boundary
- explicit HTTP/1.1 connection-persistence policy wired through `--http1-keep-alive` / `--no-http1-keep-alive` and reflected in `Connection: close` behavior
- bounded inbound WebSocket queueing across HTTP/1.1, HTTP/2, and HTTP/3 carriers via `--websocket-max-queue`
- Phase 3 docs, manifests, and release-root flag counts reconciled to the expanded public operator surface

Validation rerun for this checkpoint:

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_phase3_h1_websocket_operator_surface.py tests/test_http1_parser.py tests/test_http1_hardening_pass.py tests/test_server_websocket.py tests/test_phase2_cli_config_surface.py tests/test_public_api_cli_mtls_surface.py tests/test_public_api_tls_cipher_surface.py tests/test_phase9i_release_assembly_checkpoint.py tests/test_release_gates.py tests/test_phase8_promotion_targets.py`
- `PYTHONPATH=src python -c "from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target; ..."`

Observed results:

- compileall: **passed**
- targeted pytest bundle: **43 passed**
- `evaluate_release_gates('.')`: **passed**
- `evaluate_release_gates(... strict_target ...)`: **passed**
- `evaluate_promotion_target('.')`: **passed**

Current package status after this checkpoint:

- under the canonical `0.3.9` certification boundary: **certifiably fully RFC compliant**
- under the canonical `0.3.9` release root: **certifiably fully featured**
- against the broader `tigrcorn_unified_policy_matrix.md` target: **not yet complete** beyond Phase 3

Validation for this checkpoint is also recorded in `docs/review/conformance/phase3_h1_and_websocket_operator_surface.current.json`.
