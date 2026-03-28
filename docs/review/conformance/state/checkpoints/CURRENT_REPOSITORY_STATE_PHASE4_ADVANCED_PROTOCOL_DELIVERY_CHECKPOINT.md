> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current Repository State — Phase 4 Advanced Protocol and Delivery Checkpoint

## Scope of this checkpoint

This checkpoint is a **Phase 4 delivery** focused on advanced protocol and delivery features that still belong to the direct app-server/runtime boundary.

Included in this checkpoint:

- Early Hints public support closure for HTTP/1.1, HTTP/2, and HTTP/3
- Alt-Svc operator surface and runtime emission
- runtime compatibility documentation and embedding improvements
- static-file delivery hardening with precompressed sidecar support
- protocol-aware example packaging and example/client pairing inventory

This checkpoint explicitly stays outside cache/freshness policy, digest/signature systems, and gateway caching/enforcement product boundaries.

## Current certification statement

- **Current internal promotion target**: not re-certified globally in this checkpoint.
- **Certifiably fully featured against the expanded program**: **no**.
- **Certifiably fully RFC compliant against the expanded program**: **no**.

## Implemented in this checkpoint

### Early Hints

Implemented and/or finalized:

- safe informational response handling for `103 Early Hints`
- Link-only preservation on 103 with connection-specific headers stripped
- cross-protocol interim response forwarding in:
  - HTTP/1.1
  - HTTP/2
  - HTTP/3
- public support artifacts under `docs/review/conformance/phase4_advanced_delivery/`

### Alt-Svc

Implemented and/or finalized:

- public CLI/config surface for explicit and automatic Alt-Svc advertisement
- response-header policy integration for emitted Alt-Svc values
- automatic H3 advertisement on non-H3 responses when UDP HTTP/3 listeners are configured
- suppression of automatic Alt-Svc advertisement on direct HTTP/3 responses
- bound-listener port synchronization so auto-generated Alt-Svc works correctly with ephemeral ports

### Runtime embedding improvements

Implemented and/or finalized:

- exported runtime compatibility matrix
- `tigrcorn.embedded.EmbeddedServer` async embedding helper
- startup/shutdown hook coverage through the embedded helper
- explicit current-runtime truth that limits the public runtime surface to supported implementations only

### Static-file delivery hardening

Implemented and/or finalized:

- safe path normalization retained
- conditional / range / HEAD behavior retained from Phase 2
- precompressed sidecar selection for `.br` and `.gz` assets
- `Vary: Accept-Encoding` handling for precompressed responses
- encoded representation length preserved for HEAD responses
- range requests continue to bypass content coding so partial-content behavior stays deterministic

### Examples and pairing inventory

Added or finalized:

- `examples/advanced_delivery/app.py`
- `examples/advanced_delivery/client_http1.py`
- `examples/advanced_delivery/client_http2.py`
- `examples/advanced_delivery/client_http3.py`
- `examples/PHASE4_PROTOCOL_PAIRING.md`
- example/client pairing inventory JSON under `docs/review/conformance/phase4_advanced_delivery/examples_matrix.json`

## Main modules touched

Primary modified or added modules:

- `src/tigrcorn/static.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http3/state.py`
- `src/tigrcorn/protocols/http3/streams.py`
- `src/tigrcorn/embedded.py`
- `src/tigrcorn/__init__.py`
- `examples/advanced_delivery/*`
- `examples/PHASE4_PROTOCOL_PAIRING.md`
- `docs/review/conformance/phase4_advanced_delivery/*`
- `docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json`
- `tests/test_phase4_advanced_protocol_delivery_checkpoint.py`

## Validation

Validation counts and targeted bundle results are recorded in:

- `docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json`

Targeted validation completed green in this checkpoint:

- `python -m compileall -q src/tigrcorn`
- focused bundle: **62 passed, 0 failed**

Focused bundle files:

- `tests/test_phase1_surface_parity_checkpoint.py`
- `tests/test_phase2_entity_semantics_checkpoint.py`
- `tests/test_phase3_transport_core_strictness_checkpoint.py`
- `tests/test_phase4_advanced_protocol_delivery_checkpoint.py`
- `tests/test_http1_hardening_pass.py`
- `tests/test_server_http1.py`
- `tests/test_server_http2.py`
- `tests/test_http2_rfc9113.py`
- `tests/test_http3_server.py`
- `tests/test_http3_rfc9114.py`
- `tests/test_http3_request_stream_state_machine.py`

## Known partials and remaining gaps

- the public runtime surface now advertises only `auto`, `asyncio`, and `uvloop`; `trio` is descoped until implemented end to end
- the checkpoint does **not** expand into RFC 9111 / RFC 5861 cache freshness policy
- the checkpoint does **not** expand into RFC 9530 digest fields or RFC 9421 HTTP message signatures
- HTTP/2 / HTTP/3 prioritization remains transport-adjacent; this checkpoint does not introduce a new prioritization control plane beyond the existing protocol core
- the repository is **not** globally re-certified as fully featured or fully RFC compliant in this checkpoint

## Practical interpretation

This zip is a strong **Phase 4 checkpoint** with:

- public Early Hints and Alt-Svc support statements
- embedded runtime packaging improvements
- stronger static-file delivery behavior
- release-oriented example/client packaging
- a targeted green validation bundle

It should be treated as:

- a valid checkpoint for continued delivery
- a substantial closure of Phase 4 advanced delivery work inside the product boundary
- **not** the final word on the broader “fully featured / fully RFC compliant” expansion program
