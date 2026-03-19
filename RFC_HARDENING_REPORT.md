# RFC hardening report

This archive was updated in place against the package-wide certification target described in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Completed in this revision

- explicit separation between local conformance, same-stack replay, and independent certification evidence
- a current canonical `0.3.6` release root that consolidates preserved evidence from the historical `0.3.2`, `0.3.6-rfc-hardening`, and `0.3.6-current` bundles
- folding of the hardening candidate RFC 8441 and HTTP/2-over-TLS scenarios into the canonical independent certification matrix
- release-gate enforcement for required RFC evidence policies, per-RFC highest-tier validation, and preserved artifact presence for independent scenarios
- package-owned TCP/TLS listener-path integration for TLS 1.3, ALPN, X.509 validation, revocation policy hooks, and mTLS
- preserved third-party `aioquic` HTTP/3 request/response artifacts for the canonical independent bundle
- preserved third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 artifacts for the canonical independent bundle
- QUIC / HTTP/3 runtime fixes required for honest third-party interoperability:
  - Initial receive-key selection across Retry and server/client directions
  - timely HTTP/3 server control-stream / SETTINGS emission
  - RFC-correct STREAM frame parsing for LEN / OFF flag combinations
  - compact QUIC session-ticket encoding for resumption interop
  - original-length ClientHello binder hashing for PSK verification
- third-party RFC 9220 adapter fixes required to decode server frames correctly and drive the CONNECT stream without racing the echo path

## Current result

The canonical release gates now pass, and the package is **certifiably fully RFC compliant under the authoritative certification boundary**.

The previously blocked RFCs are now satisfied at `independent_certification`:

- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 9204
- RFC 9220

## Remaining follow-on work

The repository still preserves broader, non-authoritative strengthening work:

- a stricter all-surfaces-independent overlay for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960
- a provisional QUIC / HTTP/3 flow-control review bundle
- a seed intermediary / proxy corpus

Those items do not change the passing authoritative release-gate result.
