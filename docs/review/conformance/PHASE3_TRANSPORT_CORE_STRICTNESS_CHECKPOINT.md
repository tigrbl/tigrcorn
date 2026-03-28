> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Phase 3 Transport-Core Strictness Checkpoint

This checkpoint focuses on transport-core strictness for the protocol surface already claimed by the package:

- RFC 9112 strict framing and response-metadata closure
- RFC 9113 stream lifecycle and frame legality closure
- RFC 9114 request/control-stream and QPACK strictness
- RFC 9000 / RFC 9001 transport, packet-space, and handshake state documentation

It does **not** widen product boundary into cache/freshness policy, integrity/trust, or gateway/enforcement features.

Machine-generated transport-core tables and preserved evidence manifests live under `docs/review/conformance/phase3_transport_core/`.
See the root current-state report for the exact implementation and validation summary for this checkpoint.
