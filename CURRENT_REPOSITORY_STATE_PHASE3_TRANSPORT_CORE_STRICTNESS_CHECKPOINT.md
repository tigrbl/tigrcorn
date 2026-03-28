> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current Repository State — Phase 3 Transport-Core Strictness Checkpoint

## Scope of this checkpoint

This checkpoint is a **Phase 3 delivery** focused on transport-core strictness for already-claimed protocol surfaces.

Included in this checkpoint:

- HTTP/1.1 framing/error matrices and bodyless-response metadata rules
- HTTP/2 explicit stream lifecycle and connection invariant tables
- HTTP/3 request/control-stream and QPACK accounting tables
- QUIC packet-space legality, recovery, connection-state, and transport-error matrices
- TLS 1.3 / QUIC handshake state table
- machine-generated checkpoint snapshot artifacts and preserved evidence manifests

This checkpoint explicitly **does not** certify the repository as globally complete against the broader expansion program, and it deliberately stays outside cache/freshness, integrity/trust, and gateway/enforcement product boundaries.

## Current certification statement

- **Current internal promotion target**: not re-certified globally in this checkpoint.
- **Certifiably fully featured against the expanded program**: **no**.
- **Certifiably fully RFC compliant against the expanded program**: **no**.

## Implemented in this checkpoint

### Runtime-exported strictness tables

Added or extended exported strictness/state tables in:

- `src/tigrcorn/protocols/http1/parser.py`
- `src/tigrcorn/protocols/http1/serializer.py`
- `src/tigrcorn/protocols/http2/state.py`
- `src/tigrcorn/protocols/http3/state.py`
- `src/tigrcorn/protocols/http3/streams.py`
- `src/tigrcorn/transports/quic/streams.py`
- `src/tigrcorn/transports/quic/recovery.py`
- `src/tigrcorn/transports/quic/connection.py`
- `src/tigrcorn/security/tls13/handshake.py`

These tables expose the current implementation boundary in machine-readable form so the checkpoint is backed by explicit, reviewable transport-state data rather than prose-only claims.

### Machine-generated transport-core snapshot

Added:

- `tools/build_phase3_transport_core_checkpoint.py`
- `docs/review/conformance/phase3_transport_core/`

The snapshot contains:

- HTTP/1.1 error matrix
- HTTP/1.1 response metadata rules
- HTTP/2 stream transition table
- HTTP/2 connection rule table
- HTTP/3 request transition table
- HTTP/3 control stream rule table
- HTTP/3 QPACK accounting rule table
- QUIC packet-space legality map
- QUIC packet-space prohibition list
- QUIC recovery rules
- QUIC connection state table
- QUIC transport error matrix
- TLS 1.3 handshake state table
- interop evidence manifest referencing preserved 0.3.9 artifacts by scenario class

### Checkpoint tests

Added:

- `tests/test_phase3_transport_core_strictness_checkpoint.py`

This checkpoint test file validates that the exported strictness tables exist, that generated artifacts are present, and that representative runtime behaviors still match the exported strictness contracts.

## Focused validation completed in this checkpoint

Completed:

- `python -m compileall -q src/tigrcorn`
- targeted transport-core bundle spanning H1, H2, H3, QPACK, QUIC, TLS/QUIC, recovery, and the new checkpoint tests

Observed result for the targeted bundle:

- **92 passed**
- **0 failed**

Targeted bundle files:

- `tests/test_phase3_transport_core_strictness_checkpoint.py`
- `tests/test_http1_rfc9112.py`
- `tests/test_http1_hardening_pass.py`
- `tests/test_http2_rfc9113.py`
- `tests/test_http2_state_machine_completion.py`
- `tests/test_http3_rfc9114.py`
- `tests/test_http3_request_stream_state_machine.py`
- `tests/test_qpack_completion.py`
- `tests/test_quic_packets_rfc9000.py`
- `tests/test_quic_stream_flow_state_machine.py`
- `tests/test_quic_tls_rfc9001.py`
- `tests/test_quic_recovery_rfc9002.py`
- `tests/test_phase3_strict_rfc_surface.py`

## Known partials and remaining gaps

- This checkpoint does **not** re-run the full independent peer matrix; it preserves and indexes existing 0.3.9 artifacts by scenario class.
- This checkpoint does **not** claim global repo-wide release-gate recertification.
- Transport-core behavior is better documented and more reviewable after this checkpoint, but explicit tables are still a description of the current implementation, not an external proof by themselves.
- Phase 4 advanced delivery features remain outside this checkpoint.

## Practical interpretation

This zip is a strong **Phase 3 checkpoint** with:

- explicit transport-core state/error tables
- machine-generated strictness artifacts
- preserved evidence manifests
- a targeted green validation bundle

It should be treated as:

- a valid checkpoint for continued delivery
- a substantial closure of Phase 3 transport-core reviewability and strictness packaging
- **not** the final word on the broader “fully featured / fully RFC compliant” expansion program
