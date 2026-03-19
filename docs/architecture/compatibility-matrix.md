# Compatibility matrix

Public boundary preserved:
- `await app(scope, receive, send)`

Canonical certification boundary:
- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`

## Implemented hosting surfaces

| Surface | Implemented in this archive | Highest shipped evidence tier | Notes |
| --- | --- | --- | --- |
| HTTP/1.1 | Yes | Independent certification | `curl` request/response artifacts are preserved in the canonical `0.3.6` independent bundle. Streaming request bodies, trailers, CONNECT relay, and buffered content coding are implemented. |
| HTTP/2 prior knowledge / h2c | Yes | Independent certification | Third-party `curl` and `python-h2` request/response artifacts are preserved. HPACK dynamic state, RFC 8441 bootstrap, CONNECT relay, server push, and buffered content coding are implemented. |
| HTTP/2 over TLS / ALPN | Yes | Independent certification | Third-party TLS HTTP/2 artifacts are folded into the canonical independent bundle. |
| HTTP/3 over QUIC | Yes | Same-stack replay plus independent handshake-only edge evidence | Request/control streams, dynamic QPACK, CONNECT relay, trailers, buffered content coding, and RFC 9220 are implemented. Declared third-party HTTP/3 certification scenarios still lack preserved artifacts. |
| WebSocket over HTTP/1.1 | Yes | Independent certification | Handshake, framing, close semantics, and preserved third-party artifacts are present. |
| WebSocket over HTTP/2 | Yes | Independent certification | RFC 8441 carrier is implemented and preserved in the canonical independent bundle. |
| WebSocket over HTTP/3 | Yes | Same-stack replay plus declared independent scenarios | RFC 9220 carrier is implemented. Preserved third-party RFC 9220 artifacts are still missing. |
| QUIC transport over UDP | Yes | Mixed | OpenSSL proves the QUIC / `h3` handshake edge independently; richer HTTP/3 axes are declared for third-party certification but still preserved only as same-stack replay. |
| TCP/TLS listener path | Yes | Local conformance plus independent downstream protocol artifacts | Package-owned TLS 1.3, ALPN selection, X.509 validation, revocation policy hooks, mTLS, and ASGI `tls` scope exposure now back the public TCP/TLS listener path. |
| Lifespan | Yes | Local conformance | ASGI lifespan startup/shutdown driver. |
| Raw framed custom transport | Yes | Local conformance | Non-RFC custom hosting surface. |
