# Independent HTTP/3 / RFC 9220 certification state

The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Outcome in this checkpoint

The previously missing third-party HTTP/3 and RFC 9220 preserved artifacts have now been regenerated, promoted into the canonical independent bundle, and enabled in `docs/review/conformance/external_matrix.release.json`.

That closes the authoritative independent-certification gap for:

- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 9204
- RFC 9220

## What the adapter and runtime closure required

The final promoted `aioquic` evidence depends on both the existing third-party adapters and several committed interoperability fixes in the runtime:

- correct QUIC Initial receive-key derivation for client/server directions and Retry handling
- timely HTTP/3 server control-stream / SETTINGS emission after handshake completion
- RFC-correct QUIC STREAM frame parsing and emission for LEN / OFF flag combinations
- compact QUIC session-ticket payload encoding to keep third-party resumption ClientHello construction within implementation limits
- PSK binder generation and verification against the original-length ClientHello bytes
- RFC 9220 adapter fixes so the client decodes server frames in client mode and waits for the server echo / close handshake instead of racing it with an immediate CLOSE frame

## Preserved scenarios now present in the canonical independent bundle

The canonical independent release bundle under
`docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-independent-certification-release-matrix/`
now contains preserved passing artifacts for all nine formerly missing third-party scenarios:

- `http3-server-aioquic-client-post`
- `http3-server-aioquic-client-post-mtls`
- `http3-server-aioquic-client-post-retry`
- `http3-server-aioquic-client-post-resumption`
- `http3-server-aioquic-client-post-zero-rtt`
- `http3-server-aioquic-client-post-migration`
- `http3-server-aioquic-client-post-goaway-qpack`
- `websocket-http3-server-aioquic-client`
- `websocket-http3-server-aioquic-client-mtls`

Those scenarios are now enabled in the canonical independent matrix.

## Current practical interpretation

Under the authoritative certification boundary, the independent HTTP/3 / RFC 9220 closure work is complete and the release gates are green.

The preserved provisional HTTP/3 gap bundle remains in-tree as a historical non-certifying review aid, but it is no longer the explanation for the current release-gate result.

## Follow-on work that remains outside this document

A stricter non-authoritative all-surfaces-independent profile still needs additional third-party evidence for RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960. That follow-on work is tracked separately in `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`.
