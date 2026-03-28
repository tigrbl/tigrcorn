> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current repository state — static delivery productionization checkpoint

This checkpoint implements **Step 4 — Productionize static delivery** on top of the dependency-declaration reconciliation checkpoint.

## Scope

Implemented in scope:

- file-stat based metadata without whole-file `Path.read_bytes()` usage
- range slicing from file offsets
- streaming file delivery for the static-file path
- best-effort `sendfile` for HTTP/1.1 where the transport permits it
- HTTP/2 streamed file-segment delivery
- HTTP/3 streamed file-segment delivery through the same file-segment path
- retention of existing ETag / conditional / range / HEAD / precompressed sidecar behavior

Not expanded in this checkpoint:

- broader RFC certification boundary changes
- generic non-static response streaming re-architecture
- cache/freshness, integrity/trust, or gateway policy scope

## Code changes

Primary code paths updated:

- `src/tigrcorn/static.py`
- `src/tigrcorn/http/range.py`
- `src/tigrcorn/http/entity.py`
- `src/tigrcorn/asgi/send.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`
- `tests/test_static_delivery_productionization_checkpoint.py`

## What is now true

- `StaticFilesApp` no longer uses `Path.read_bytes()` in the steady-state large-file path
- static metadata is derived from file stats plus incremental digesting for representation ETags
- file responses are represented as explicit memory/file segments in the ASGI response pipeline
- HTTP/1.1 can use a best-effort zero-copy `sendfile` path and otherwise falls back to streamed file reads
- HTTP/2 streams file-backed body segments without materializing the full representation in memory
- HTTP/3 uses the same file-segment response path; the large-response test drives normal QUIC client progress so anti-amplification and recovery pacing remain respected
- range slicing is planned directly from file offsets, including multipart range assembly without full file buffering
- precompressed `.br` / `.gz` sidecars, conditional requests, byte ranges, and `HEAD` behavior remain preserved

## Known partials

- on-the-fly dynamic content coding remains intentionally buffered and size-limited to small static representations
- the broader generic app-response entity pipeline is still buffered outside the static-file path
- HTTP/3 large responses remain subject to QUIC anti-amplification and require normal client ACK/timer progress; this checkpoint does not bypass those transport rules

## Validation completed in this checkpoint

- `python -m compileall -q src benchmarks tools` → passed
- targeted pytest bundle → `31 passed, 0 failed`
- `evaluate_release_gates('.')` → passed
- `evaluate_release_gates(... strict_target ...)` → passed
- `evaluate_promotion_target('.')` → passed

Targeted pytest bundle:

- `tests/test_phase1_surface_parity_checkpoint.py`
- `tests/test_phase2_entity_semantics_checkpoint.py`
- `tests/test_phase4_advanced_protocol_delivery_checkpoint.py`
- `tests/test_static_delivery_productionization_checkpoint.py`
- `tests/test_server_http1.py`
- `tests/test_server_http2.py`
- `tests/test_http3_server.py`

## Honest status

- this checkpoint materially improves the static-file delivery path and removes the previous steady-state `read_bytes()` / whole-file buffering implementation from that path
- within the repository's current declared authoritative / strict / promotion model, the package remains green after this checkpoint
- this checkpoint does **not** newly certify additional RFC targets beyond the current declared model
