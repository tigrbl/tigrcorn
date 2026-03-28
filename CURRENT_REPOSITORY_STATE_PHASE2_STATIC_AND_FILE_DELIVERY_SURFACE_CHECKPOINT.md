# Phase 2 static and file-delivery surface checkpoint

This checkpoint completes the server-native static delivery surface inside the current T/P/A/D/R boundary.

What landed:

- public CLI/config/env controls for `--static-path-route`, `--static-path-mount`, `--static-path-dir-to-file`, `--no-static-path-dir-to-file`, `--static-path-index-file`, and `--static-path-expires`
- runtime composition of mounted static delivery through `mount_static_app(...)` when configured from CLI/config
- standard ASGI `http.response.pathsend` support in the response collector/writer path
- `http.response.pathsend` advertisement on HTTP/1.1, HTTP/2, and HTTP/3 request scopes
- `StaticFilesApp` remains supported as the package-owned application surface while the server-native operator surface now exists in parallel
- static/operator docs, manifests, and release-root flag counts reconciled to the expanded public surface

Validation rerun for this checkpoint:

- `python -m compileall -q src benchmarks tools`
- `PYTHONPATH=src pytest -q tests/test_phase2_cli_config_surface.py tests/test_phase2_static_delivery_surface.py tests/test_static_delivery_productionization_checkpoint.py tests/test_phase9i_release_assembly_checkpoint.py tests/test_release_gates.py tests/test_phase8_promotion_targets.py`
- `PYTHONPATH=src python -c "from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target; ..."`

Observed results:

- compileall: **passed**
- targeted pytest bundle: **30 passed**
- `evaluate_release_gates('.')`: **passed**
- `evaluate_release_gates(... strict_target ...)`: **passed**
- `evaluate_promotion_target('.')`: **passed**

Current package status after this checkpoint:

- under the canonical `0.3.9` certification boundary: **certifiably fully RFC compliant**
- under the canonical `0.3.9` release root: **certifiably fully featured**
- against the broader `tigrcorn_unified_policy_matrix.md` target: **not yet complete** beyond Phase 2

Validation for this checkpoint is also recorded in `docs/review/conformance/phase2_static_and_file_delivery_surface.current.json`.
