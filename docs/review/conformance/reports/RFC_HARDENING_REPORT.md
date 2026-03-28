# RFC hardening report

This repository has been hardened and promoted against the package-wide certification target defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Completed on the promoted line

- clear separation between local conformance, same-stack replay, and independent certification evidence
- preserved historical `0.3.8` release artifacts alongside the promoted canonical `0.3.9` release root
- package-owned TCP/TLS listener-path integration for TLS 1.3, ALPN, X.509 path validation, OCSP/CRL policy hooks, and mTLS
- preserved third-party `aioquic` HTTP/3 request/response artifacts for the canonical independent bundle
- preserved third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 artifacts for the canonical independent bundle
- QUIC / HTTP/3 runtime fixes required for honest third-party interoperability:
  - Initial receive-key selection across Retry and server/client directions
  - timely HTTP/3 server control-stream / SETTINGS emission
  - RFC-correct STREAM frame parsing for LEN / OFF flag combinations
  - compact QUIC session-ticket encoding for resumption interop
  - original-length ClientHello binder hashing for PSK verification
- RFC 7692, CONNECT, trailer, content-coding, TLS material, lifecycle/embedder, and operator-surface closure work folded into the promoted `0.3.9` line

## Current result

The canonical release gates pass, and the package is **certifiably fully RFC compliant under the authoritative certification boundary**.

The promoted `0.3.9` release root is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

## Release roots

Canonical promoted root:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/`

Historical preserved released root:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/`

## Follow-on posture

The current line has no remaining in-bounds certification blockers.

Future work must begin by deciding whether it is:

- in-boundary patch work
- boundary expansion requiring a minor-version decision
- explicitly outside the current boundary per `docs/review/conformance/BOUNDARY_NON_GOALS.md`
