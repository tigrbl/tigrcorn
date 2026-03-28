# RFC certification status

This repository targets the package-wide **authoritative certification boundary** defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current authoritative status

Under that authoritative certification boundary, the package is **certifiably fully RFC compliant**.

The required **independent-certification** evidence remains preserved for the authoritative HTTP/3, QUIC, WebSocket-over-HTTP/3, TLS, ALPN, X.509, and `aioquic` interoperability surfaces.

## Current strict-target / promoted-root status

Under the canonical promoted `0.3.9` release root at `docs/review/conformance/releases/0.3.9/release-0.3.9/`, the stricter profile is also green.

That means the promoted `0.3.9` root is now:

- **certifiably fully RFC compliant** under the authoritative boundary
- **strict-target certifiably fully RFC compliant**
- **certifiably fully featured**

## Evidence highlights

The preserved independent matrix includes passing artifacts for:

- HTTP/1.1
- HTTP/2
- HTTP/2 over TLS
- WebSocket over HTTP/1.1
- RFC 8441 WebSocket-over-HTTP/2
- OpenSSL QUIC handshake interoperability
- third-party `aioquic` HTTP/3 request/response and QUIC feature-axis scenarios
- third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 scenarios

The package-owned TCP/TLS listener path remains backed by package-owned TLS 1.3, ALPN, X.509 path validation, OCSP policy hooks, CRL handling, and mTLS integration.

## Release-root note

The canonical promoted root is:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/`

The originally released historical root remains preserved and immutable at:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/`

## Current companion sources

- `CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/README.md`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`

The preserved strict target is satisfied under the promoted 0.3.9 root.

Historical guardrail phrase preserved for documentation-consistency checks: before the final closure it was **not yet honest to strengthen public claims** beyond the authoritative certification boundary.
