# Phase 4 HTTP/2 operator-surface checkpoint

This checkpoint completes the missing HTTP/2 operator-grade controls inside the current T/P/A/D/R boundary.

What landed:

- public CLI/config/env controls for `--http2-max-concurrent-streams`, `--http2-max-headers-size`, `--http2-max-frame-size`, `--http2-adaptive-window`, `--no-http2-adaptive-window`, `--http2-initial-connection-window-size`, `--http2-initial-stream-window-size`, `--http2-keep-alive-interval`, and `--http2-keep-alive-timeout`
- package-owned HTTP/2 local SETTINGS advertisement for max concurrent streams, max header-list size, max frame size, and initial stream receive window
- package-owned HTTP/2 connection receive-window initialization above the default through a matching stream-0 `WINDOW_UPDATE` increment
- package-owned adaptive HTTP/2 receive-window growth for connection and stream windows when `--http2-adaptive-window` is enabled
- package-owned HTTP/2 connection keepalive scheduling through outbound PING frames with timeout-driven connection closure
- Phase 4 docs, manifests, and release-root flag counts reconciled to the expanded public operator surface

Validation rerun for this checkpoint:

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_phase4_http2_operator_surface.py tests/test_phase2_cli_config_surface.py tests/test_phase8_promotion_targets.py tests/test_phase9i_release_assembly_checkpoint.py tests/test_release_gates.py`
- `PYTHONPATH=src python -c "from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target; ..."`

Observed results:

- compileall: **passed**
- targeted pytest bundle: **29 passed**
- `evaluate_release_gates('.')`: **passed**
- `evaluate_release_gates(... strict_target ...)`: **passed**
- `evaluate_promotion_target('.')`: **passed**

Current package status after this checkpoint:

- under the canonical `0.3.9` certification boundary: **certifiably fully RFC compliant**
- under the canonical `0.3.9` release root: **certifiably fully featured**
- against the broader `tigrcorn_unified_policy_matrix.md` target: **not yet complete** beyond Phase 4

Validation for this checkpoint is also recorded in `docs/review/conformance/phase4_h2_operator_surface.current.json`.
