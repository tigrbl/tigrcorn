# HTTP/2

# HTTP/2

This build includes a pure-Python HTTP/2 prior-knowledge server path with an explicit RFC 9113 stream-state machine.

## Implemented and validated in this build

- frame encoding and decoding
- SETTINGS, HEADERS, CONTINUATION, DATA, WINDOW_UPDATE, PING, GOAWAY, PRIORITY, and RST_STREAM handling
- explicit stream lifecycle tracking for `idle`, `reserved-local`, `reserved-remote`, `open`, `half-closed-local`, `half-closed-remote`, and `closed`
- first-frame `SETTINGS` enforcement after the client connection preface
- stream-state-specific legality checks for HEADERS, DATA, WINDOW_UPDATE, CONTINUATION, PRIORITY, GOAWAY, and RST_STREAM
- max concurrent stream enforcement
- monotonic GOAWAY handling and rejection of new inbound streams after GOAWAY
- receive-side flow-control accounting with thresholded WINDOW_UPDATE emission instead of immediate echo updates
- bounded request buffering using configured header/body size limits
- CONTINUATION/header-block lifecycle enforcement, including strict same-stream continuation sequencing
- request-header validation for pseudo-header ordering, duplicates, lowercase field names, and forbidden connection-specific fields
- HPACK dynamic table support with differential coverage
- RFC 8441 extended CONNECT bootstrap for WebSocket-over-HTTP/2
- outbound server push via `PUSH_PROMISE` and promised response streams on the HTTP/2 carrier
- per-stream request dispatch onto the ASGI boundary
- generic CONNECT tunnel relay integration on the HTTP/2 carrier

## Release evidence shipped with this archive

Historical preserved evidence remains bundled:

- `curl --http2-prior-knowledge` request/response artifacts under `docs/review/conformance/releases/0.3.2/.../http2-server-curl-client/`
- `curl` HTTPS + ALPN HTTP/2 request/response artifacts under `docs/review/conformance/releases/0.3.6-rfc-hardening/.../http2-tls-server-curl-client/`
- third-party `h2` WebSocket extended CONNECT artifacts under `docs/review/conformance/releases/0.3.6-rfc-hardening/.../websocket-http2-server-h2-client/`

The committed current-release bundle at `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/tigrcorn-current-release-matrix/` additionally includes replayable `python-h2` request/response artifacts for both cleartext and TLS hosting.

## Evidence status

The documentation for the HTTP/2 carrier is aligned with the implemented code and the committed release bundle. HPACK dynamic state, RFC 8441, TLS hosting, and CONNECT relay are all represented in preserved and current evidence.
