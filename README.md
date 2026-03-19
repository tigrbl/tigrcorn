# tigrcorn

`tigrcorn` is an ASGI3-compatible transport server implemented with package-owned protocol/runtime code.

```python
async def app(scope, receive, send):
    ...
```

## Implemented surfaces in this archive

- HTTP/1.1 server path with streaming request bodies
- HTTP/1.1, HTTP/2, and HTTP/3 CONNECT relay tunneling
- trailer-field exposure on the HTTP/1.1, HTTP/2, and HTTP/3 request paths through an extension event
- HTTP content-coding negotiation for buffered responses (`gzip`, `deflate`, and `br` when Brotli support is present)
- WebSocket upgrade and frame processing over HTTP/1.1
- WebSocket permessage-deflate on the HTTP/1.1, HTTP/2, and HTTP/3 paths
- HTTP/2 codec, HPACK dynamic state, RFC 8441 WebSocket bootstrap, server push, and prior-knowledge server path
- RFC 9220 WebSocket bootstrap on the HTTP/3 carrier
- QUIC transport helpers, QUIC-TLS handshake support, session tickets, Retry, resumption, 0-RTT, migration handling, and HTTP/3 over UDP through the public API and CLI
- public mTLS-style client-certificate configuration for TLS and QUIC-TLS listeners through `ssl_ca_certs` and `ssl_require_client_cert`
- QPACK encoder/decoder streams and dynamic state
- certificate path validation, OCSP, CRL, and ALPN helpers in the package security subsystem
- package-owned TLS 1.3 server path on TCP/Unix listeners with record protection, ALPN selection, X.509 path validation, OCSP/CRL policy hooks, mTLS, and ASGI `tls` scope exposure
- TCP, Unix, UDP, pipe, and in-process listener implementations
- raw framed custom transport hosting path

## Canonical certification boundary

The package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

That boundary names the required RFC surface for RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 7541, RFC 9204, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 8446, RFC 9110 CONNECT semantics, RFC 9110 trailer fields, RFC 9110 content coding, RFC 5280, RFC 6960, and RFC 7301.

## Evidence tiers shipped with this archive

This archive separates three evidence tiers and binds them to a single current release root:

1. **Local conformance** — `docs/review/conformance/corpus.json`
2. **Same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`
3. **Independent certification** — `docs/review/conformance/external_matrix.release.json`

The current canonical release root is `docs/review/conformance/releases/0.3.6/release-0.3.6/`.

That root contains:

- `tigrcorn-independent-certification-release-matrix/`
- `tigrcorn-same-stack-replay-matrix/`
- `tigrcorn-mixed-compatibility-release-matrix/`
- `tigrcorn-provisional-http3-gap-bundle/` (a preserved non-certifying historical review bundle from the pre-closure gap state)
- `tigrcorn-provisional-all-surfaces-gap-bundle/` (a preserved non-certifying stricter-profile planning bundle)
- `tigrcorn-provisional-flow-control-gap-bundle/` (a preserved non-certifying QUIC / HTTP/3 flow-control review bundle)

The compatibility file `docs/review/conformance/external_matrix.current_release.json` is still preserved as a **mixed** matrix because it combines third-party HTTP/1.1 / HTTP/2 peers with same-stack HTTP/3 and RFC 9220 replay fixtures. The legacy `0.3.2`, `0.3.6-rfc-hardening`, and `0.3.6-current` bundles remain in-tree for provenance, but the `0.3.6` root is now the canonical current release bundle.

## Interoperability evidence status in this archive

The canonical independent matrix now includes preserved passing artifacts for:

- HTTP/1.1, HTTP/2, HTTP/2 over TLS, WebSocket over HTTP/1.1, WebSocket over HTTP/2, and QUIC handshake interoperability
- third-party `aioquic` HTTP/3 request/response, mTLS, Retry, resumption, 0-RTT, migration, and GOAWAY / QPACK scenarios
- third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 scenarios

The package-owned TCP/TLS listener path is backed by package-owned TLS 1.3, ALPN, X.509 validation, revocation policy hooks, and mTLS integration.

As a result, the canonical release gates now pass and the package is **certifiably fully RFC compliant under the authoritative certification boundary** in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

Important scope note:

- Under the current authoritative boundary, RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 are intentionally bounded at `local_conformance` rather than `independent_certification`.
- Those surfaces are still part of the required RFC surface, and they are satisfied at the tier required by the boundary.
- A stricter non-authoritative all-surfaces-independent profile would still need additional third-party preserved artifacts.
- The provisional all-surfaces and flow-control bundles remain in-tree as planning / review aids and do not change the authoritative release-gate result.

For the point-in-time repository summary, see `CURRENT_REPOSITORY_STATE.md`. For the machine-readable certification policy, see `docs/review/conformance/certification_boundary.json`. For the offline remediation attempt that produced the provisional bundles, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`.

## Running

```bash
python -m tigrcorn examples.echo_http.app:app
```

UDP / HTTP/3 example with QUIC-TLS certificates:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem
```

UDP / HTTP/3 example with client-certificate verification enabled:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --ssl-ca-certs client-ca.pem --ssl-require-client-cert
```

UDP / HTTP/3 example with Retry enabled:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --quic-require-retry
```
