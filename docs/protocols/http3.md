# HTTP/3

This repository includes a stdlib-only HTTP/3 core integrated with the bundled QUIC transport.

## Implemented and locally validated in this build

- frame codec
- settings codec
- request-stream parsing and control-stream validation
- QPACK encoder stream, decoder stream, and dynamic table state
- UDP server integration over the bundled QUIC transport core
- public API / CLI startup for certificate-driven QUIC-TLS listeners
- QUIC Retry exposure through the public configuration surface
- QUIC-TLS session-ticket issuance, resumption, and 0-RTT handling in the runtime
- request-trailer propagation on the ASGI request path
- response content-coding negotiation for buffered responses
- generic CONNECT tunnel relay integration on the HTTP/3 carrier
- RFC 9220 WebSocket bootstrap and framed carrier integration on HTTP/3 request streams

## Evidence tiers

The canonical certification boundary for this carrier is `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

HTTP/3 evidence is split explicitly:

- **local conformance** — `tests/test_http3_rfc9114.py`, `tests/test_qpack_completion.py`, `tests/test_http3_websocket_rfc9220.py`, `tests/test_connect_rfc9110.py`, `tests/test_trailers_rfc9110.py`, and `tests/test_http_content_coding_rfc9110.py`
- **same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json` and the canonical same-stack bundle under `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-same-stack-replay-matrix/`
- **independent certification** — `docs/review/conformance/external_matrix.release.json` and the canonical independent bundle under `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-independent-certification-release-matrix/`

## Current certification status

The independent matrix now contains preserved passing third-party HTTP/3 request/response, mTLS, Retry, resumption, 0-RTT, migration, GOAWAY / QPACK, and RFC 9220 scenarios.

Under the authoritative certification boundary, the HTTP/3 carrier is now satisfied at the required tier:

- RFC 9114 is satisfied at `independent_certification`
- RFC 9204 is satisfied at `independent_certification`
- the related QUIC transport RFCs used by the HTTP/3 carrier are satisfied at `independent_certification`
- package-owned TCP/TLS condition in the certification boundary is satisfied separately

The stricter all-surfaces-independent overlay remains a separate non-authoritative follow-on profile.
