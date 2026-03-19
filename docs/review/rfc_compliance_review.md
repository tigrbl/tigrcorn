# QUIC-TLS and WebPKI hardening review

The canonical package-wide certification target for the current repository is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

The current canonical release root is `docs/review/conformance/releases/0.3.6/release-0.3.6/`.

That current release root consolidates the independent certification bundle, the same-stack replay bundle, and the mixed compatibility bundle for version 0.3.6 while preserving the older `0.3.2`, `0.3.6-rfc-hardening`, and `0.3.6-current` trees for provenance.

This repository now contains two major security passes:

1. a real binary TLS 1.3 handshake subsystem for QUIC-TLS
2. a stricter WebPKI-style X.509 path validator for peer certificate verification

## TLS 1.3 / QUIC-TLS pass

### What changed
- `src/tigrcorn/security/tls13/messages.py`
  - binary TLS 1.3 handshake message encode/decode for `ClientHello`, `ServerHello`, `EncryptedExtensions`, `Certificate`, `CertificateVerify`, `Finished`, `NewSessionTicket`, `KeyUpdate`, and transcript `message_hash`
- `src/tigrcorn/security/tls13/extensions.py`
  - binary TLS extension handling for supported versions, key share, signature algorithms, ALPN, early data, PSK identities/binders, and QUIC transport parameters
- `src/tigrcorn/security/tls13/transcript.py`
  - transcript hashing and HelloRetryRequest message-hash reset handling
- `src/tigrcorn/security/tls13/key_schedule.py`
  - RFC 8446 label-based HKDF derivation for early, handshake, application, exporter, resumption, binder, finished, and traffic-update secrets
- `src/tigrcorn/security/tls13/handshake.py`
  - client/server TLS 1.3 handshake state transitions over QUIC CRYPTO
  - QUIC transport-parameter negotiation
  - `CertificateVerify` and `Finished` validation
  - `NewSessionTicket` issuance and consumption
  - PSK binder and ticket-age checks
  - QUIC 0-RTT replay gate
  - TLS `KeyUpdate` rejection on QUIC
- `src/tigrcorn/transports/quic/tls_adapter.py`
  - maps TLS encryption levels/messages onto QUIC Initial, Handshake, and 1-RTT packet spaces

### QUIC integration updates
- `src/tigrcorn/transports/quic/handshake.py`
  - compatibility export surface for the TLS 1.3 engine
- `src/tigrcorn/transports/quic/connection.py`
  - installs handshake traffic keys immediately after `ServerHello`
  - maps TLS alerts to QUIC transport errors on the CRYPTO path

## WebPKI certificate path validation pass

### What changed
- `src/tigrcorn/security/x509/path.py`
  - replaces the handwritten chain walker with `cryptography.x509.verification` WebPKI policy validation
  - enforces WebPKI-style trust-anchor and path-building semantics
  - enforces BasicConstraints, KeyUsage, ExtendedKeyUsage, name constraints, and critical-extension rules through the verifier policy
  - requires SAN-based hostname/IP validation for server certificates
  - uses UTC-aware certificate validity accessors
  - adds revocation policy hooks with offline CRL and OCSP evidence handling
- `src/tigrcorn/security/tls.py`
  - now exposes the stricter validation policy types for callers
- `src/tigrcorn/security/tls13/handshake.py`
  - self-signed test certificates now include SubjectKeyIdentifier and AuthorityKeyIdentifier so they are valid trust-anchor test fixtures under the stricter validator

### Validation evidence added
- `tests/test_tls13_engine_upgrade.py`
  - binary TLS `ClientHello` carries QUIC transport parameters
  - HelloRetryRequest is emitted when the client omits the required key share
  - session tickets enable PSK resumption and QUIC 0-RTT when policy permits
  - 0-RTT ticket replay is rejected on reuse
  - TLS `KeyUpdate` is rejected for QUIC
- `tests/test_x509_webpki_validation.py`
  - directly trusted self-signed leaf with SAN/SKI/AKI succeeds
  - leaf without SAN is rejected even if CN matches
  - path-length violations are rejected
  - name-constraints violations are rejected
  - revoked leaf certificates are rejected when a CRL is supplied
  - revocation-required policy fails when no revocation evidence is available

## QUIC transport runtime completion pass

### What changed
- `src/tigrcorn/transports/quic/streams.py`
  - added runtime support and binary encode/decode for `NEW_TOKEN`, `DATA_BLOCKED`, `STREAM_DATA_BLOCKED`, `STREAMS_BLOCKED`, and application-vs-transport `CONNECTION_CLOSE`
  - added legality checks by packet number space and endpoint role
- `src/tigrcorn/transports/quic/packets.py`
  - added packet-wire-length calculation, coalesced datagram splitting, and datagram packet coalescing helpers
- `src/tigrcorn/transports/quic/connection.py`
  - added coalesced-datagram receive and packet builder support
  - added real QUIC `0-RTT` packet encode/decode paths
  - added Version Negotiation generation/handling
  - added Retry token issuance, validation, expiry, and client Retry processing
  - added `NEW_TOKEN` issuance/consumption and address-validation token handling
  - added `original_destination_connection_id`, `retry_source_connection_id`, and `initial_source_connection_id` transport-parameter enforcement
  - added runtime handling for `disable_active_migration` and `preferred_address`
  - added explicit application-vs-transport close-event surfacing
  - added short-header decode fallback across known CID lengths so runtime CID changes and custom QUIC probes can be decoded correctly
- `src/tigrcorn/protocols/http3/handler.py`
  - now passes sender addresses into QUIC runtime processing so path validation and migration policy are enforced before rebinding session state
- `src/tigrcorn/security/tls13/handshake.py`
  - now derives the server-side client early-traffic secret during PSK acceptance so QUIC `0-RTT` packets can be decrypted immediately after `ClientHello`

### Validation evidence added
- `tests/test_quic_transport_runtime_completion.py`
  - coalesced Initial packets are parsed from a single UDP datagram
  - Version Negotiation packets are generated and consumed
  - Retry roundtrips validate tokens and NEW_TOKEN frames are delivered to peers
  - QUIC `0-RTT` stream data decrypts after `ClientHello` on resumed sessions
  - blocked-frame types and application close events surface at runtime
  - `disable_active_migration` violations close the connection and server `preferred_address` is reported to the client

## QUIC stream and flow-control state-machine pass

### What changed
- `src/tigrcorn/transports/quic/streams.py`
  - replaces the old byte-reassembly-only stream model with explicit send-side and receive-side stream states
  - enforces bidirectional vs unidirectional stream roles
  - enforces peer-initiated stream limits and tracks stream lifecycle for `MAX_STREAMS` recycling
  - preserves out-of-order reassembly while enforcing final-size invariants across `STREAM` and `RESET_STREAM`
- `src/tigrcorn/transports/quic/flow.py`
  - replaces the single-window model with distinct peer-advertised send credit and locally advertised receive credit
  - tracks connection-level and stream-level send and receive accounting separately
  - applies distinct default windows for `initial_max_stream_data_bidi_local`, `initial_max_stream_data_bidi_remote`, and `initial_max_stream_data_uni`
  - validates receive-side flow control using highest observed offsets and reset final sizes
- `src/tigrcorn/transports/quic/connection.py`
  - integrates the new stream manager and flow controller into the live runtime
  - auto-emits `DATA_BLOCKED`, `STREAM_DATA_BLOCKED`, and `STREAMS_BLOCKED` when local send paths hit peer credit/stream limits
  - emits `MAX_STREAMS` credit updates when peer-initiated streams close
  - maps `STOP_SENDING` to local `RESET_STREAM` generation when the local send side is still open
  - uses the locally negotiated `ack_delay_exponent` when encoding ACK delays
  - separates local receive-credit expansion (`MAX_DATA` / `MAX_STREAM_DATA`) from peer send-credit updates

### Validation evidence added
- `tests/test_quic_stream_flow_state_machine.py`
  - peer-initiated stream limits are enforced
  - send attempts on receive-only unidirectional streams are rejected
  - distinct bidi-local, bidi-remote, and uni flow-control windows govern the correct stream classes
  - receive-side flow control rejects oversized stream data and oversized reset final sizes
  - `STOP_SENDING` triggers a pending `RESET_STREAM`
  - closed peer-initiated streams recycle `MAX_STREAMS` credit
  - ACK encoding uses the locally negotiated `ack_delay_exponent`
  - `credit_connection()` / `credit_stream()` expand local receive credit without mutating peer send credit

## QUIC RFC 9002 live runtime integration pass

### What changed
- `src/tigrcorn/transports/quic/recovery.py`
  - added packet activation/deactivation so recovery accounting can follow actual wire transmission instead of packet creation time alone
  - added pacing-budget refunds and re-spend on deferred vs confirmed transmission
  - added PTO candidate enumeration and pacing-delay estimation for live schedulers
- `src/tigrcorn/transports/quic/scheduler.py`
  - added a connection-level timer wheel used for ACK, loss, and PTO timers
- `src/tigrcorn/transports/quic/connection.py`
  - added path-specific recovery contexts keyed by observed peer addresses
  - tracks sent packet metadata by packet number space so ACK processing can drive retransmission selection
  - schedules delayed ACKs, loss timers, and PTO alarms through a central timer wheel
  - turns loss detection results into retransmission frame scheduling
  - turns PTO expiry into probe packet scheduling
  - exposes deferred/confirmed datagram transmission hooks so pacing and anti-amplification decisions can be made at actual UDP-send time
  - prevents invalid coalescing of multiple short-header packets into one datagram
- `src/tigrcorn/protocols/http3/handler.py`
  - now defers outbound datagrams that are recovery-blocked instead of sending immediately
  - now confirms transmission only when a datagram is actually emitted on the UDP endpoint
  - now arms per-session timer callbacks so paced sends, ACK deadlines, loss recovery, and PTO probes continue even when no new inbound packets arrive

### Validation evidence added
- `tests/test_quic_recovery_live_runtime_integration.py`
  - ACK-driven loss detection schedules retransmission packets
  - PTO expiry produces probe traffic
  - recovery state is separated per observed path after rebinding
  - the HTTP/3 runtime defers and later flushes recovery-blocked outbound datagrams

## Repository status for these passes
- `155 passed`

## Honest boundary

These passes materially strengthen tigrcorn's TLS and certificate-validation surfaces.

They do **not** by themselves justify a claim that the entire package is independently certified and fully RFC-complete across HTTP/1.1, WebSocket, HTTP/2, HPACK, QUIC transport, QUIC-TLS, HTTP/3, and QPACK.

At this point in the review history the remaining work was concentrated in the broader transport/runtime/interoperability areas:
- external interoperability evidence against independent peers was still required
- the wider QUIC transport, HTTP/3, QPACK, HTTP/2, and HPACK state machines still needed their own completion and audit paths
- production revocation distribution, cache management, freshness policy, and online fetch strategy were still not built out beyond supplied offline evidence

## HTTP/3 RFC 9114 request/control stream state-machine pass

### What changed
- `src/tigrcorn/protocols/http3/codec.py`
  - added explicit HTTP/3 application error-code constants and typed `HTTP3ConnectionError` / `HTTP3StreamError` surfaces
  - rejects reserved HTTP/3 SETTINGS identifiers with `H3_SETTINGS_ERROR`
  - added strict single-varint payload decoding helpers for control-stream frame validation
- `src/tigrcorn/protocols/http3/state.py`
  - replaced the minimal request-state placeholder with explicit request/body/trailer/QPACK-blocked state
  - added push-promise bookkeeping and control-stream GOAWAY / MAX_PUSH_ID / CANCEL_PUSH state
- `src/tigrcorn/protocols/http3/streams.py`
  - replaced the permissive request-stream parser with an RFC 9114-shaped state machine
  - rejects `DATA` before initial `HEADERS`
  - rejects `HEADERS` / `DATA` after trailing `HEADERS`
  - preserves the RFC rule that unknown and reserved frame types are ignored on request streams
  - enforces request-side `Content-Length` consistency against received `DATA` bytes
  - distinguishes request-stream connection errors (`H3_FRAME_UNEXPECTED`) from malformed-request stream errors (`H3_MESSAGE_ERROR`, `H3_REQUEST_INCOMPLETE`)
  - requires SETTINGS as the first frame on the control stream and rejects duplicate SETTINGS
  - validates GOAWAY monotonicity and server-direction stream-ID type constraints
  - validates MAX_PUSH_ID monotonicity and role legality
  - validates CANCEL_PUSH references and role legality
  - rejects PUSH_PROMISE on server-side request streams while preserving client-side storage hooks
  - maps critical-stream closure to `H3_CLOSED_CRITICAL_STREAM`
  - adds local GOAWAY-based request rejection with `H3_REQUEST_REJECTED`
- `src/tigrcorn/protocols/http3/handler.py`
  - server-side HTTP/3 sessions now instantiate the connection core in `role='server'`
  - maps HTTP/3 stream errors to QUIC `RESET_STREAM`
  - maps HTTP/3 connection errors to QUIC application `CONNECTION_CLOSE`
  - no longer silently ignores malformed HTTP/3 request/control-stream protocol violations
- `src/tigrcorn/protocols/http3/__init__.py`
  - exports the new HTTP/3 error surfaces and stricter state types

### Validation evidence added
- `tests/test_http3_request_stream_state_machine.py`
  - request streams reject `DATA` before `HEADERS`
  - request streams reject `DATA` after trailing `HEADERS`
  - malformed `Content-Length` completion produces `H3_MESSAGE_ERROR`
  - unknown frame types are ignored on request streams without corrupting state
  - control streams require SETTINGS as the first frame
  - reserved SETTINGS identifiers fail with `H3_SETTINGS_ERROR`
  - server-side request streams reject PUSH_PROMISE
  - GOAWAY identifiers are enforced as non-increasing
  - the live HTTP/3 runtime resets malformed request streams with the correct HTTP/3 error code

## Repository status for these passes
- `164 passed`

## QPACK RFC 9204 completion pass

### What changed
- `src/tigrcorn/protocols/http3/qpack.py`
  - added dedicated QPACK decompression / encoder-stream / decoder-stream error types
  - enforces `SETTINGS_QPACK_BLOCKED_STREAMS` on both the encoder decision path and decoder blocked-stream accounting
  - uses the encoder `Known Received Count` as the boundary between acknowledged-vs-risky dynamic references
  - tracks outstanding field sections per stream and releases references strictly on section acknowledgment or stream cancellation
  - prevents encoder-side dynamic-table eviction of entries that still have outstanding references or that are not yet known received
  - tightens decoder validation for invalid dynamic references, invalid static indexes, invalid insert-count increments, and invalid encoder-stream instructions
  - adds decoder-side stream-cancellation support for abandoned blocked streams
- `src/tigrcorn/protocols/http3/streams.py`
  - request-stream parsing now applies QPACK backpressure correctly: once a blocked header section is encountered, later frames remain buffered until the section unblocks
  - blocked request streams can now be abandoned cleanly, generating QPACK Stream Cancellation on the decoder stream
  - invalid QPACK field sections now map to `QPACK_DECOMPRESSION_FAILED`
  - invalid QPACK encoder/decoder stream instructions now map to `QPACK_ENCODER_STREAM_ERROR` / `QPACK_DECODER_STREAM_ERROR`
- `src/tigrcorn/protocols/http3/handler.py`
  - HTTP/3 stream resets and local request-abandon paths now notify the QPACK decoder so blocked references are released through decoder-stream cancellation
- `src/tigrcorn/protocols/http3/codec.py`
  - exports QPACK application error-code constants
- `src/tigrcorn/protocols/http3/state.py`
  - request state now tracks explicit abandonment so blocked/cancelled requests cannot become ready later
- `src/tigrcorn/protocols/http3/__init__.py`
  - exports the new QPACK error surfaces and constants

### Validation evidence added
- `tests/test_qpack_completion.py`
  - the encoder stops creating new blocked streams once the peer's blocked-stream budget is exhausted
  - encoder indexing is deferred when an insert would evict an entry still referenced by an outstanding field section
  - extra section acknowledgments fail with decoder-stream error semantics
  - HTTP/3 request-stream buffering preserves DATA/trailer bytes behind a blocked initial HEADERS section until QPACK unblocks
  - invalid QPACK encoder stream, decoder stream, and field-section inputs map to the correct HTTP/3/QPACK connection error codes
  - post-base references decode correctly
  - Required Insert Count wraparound decodes correctly

## Repository status for these passes
- `171 passed`

## HTTP/2 RFC 9113 stream-state-machine completion pass

### What changed
- `src/tigrcorn/protocols/http2/state.py`
  - replaced the boolean-only stream record with explicit RFC-shaped lifecycle states:
    - `idle`
    - `reserved-local`
    - `reserved-remote`
    - `open`
    - `half-closed-local`
    - `half-closed-remote`
    - `closed`
  - added connection-level and stream-level receive-window accounting alongside the existing send-window state
  - added explicit GOAWAY bookkeeping and local/remote flow-control targets
- `src/tigrcorn/protocols/http2/streams.py`
  - added active-stream and closed-stream tracking so legality checks can distinguish idle from closed streams
  - applies peer `INITIAL_WINDOW_SIZE` deltas to all live outbound stream send windows with overflow checks
- `src/tigrcorn/protocols/http2/codec.py`
  - added HTTP/2 error-code constants and PRIORITY parsing support used by the stricter runtime
- `src/tigrcorn/protocols/http2/handler.py`
  - enforces that the first frame after the client preface is `SETTINGS`
  - validates stream-state legality for HEADERS, DATA, WINDOW_UPDATE, CONTINUATION, PRIORITY, PUSH_PROMISE, RST_STREAM, and GOAWAY
  - enforces monotonic client stream IDs and `SETTINGS_MAX_CONCURRENT_STREAMS`
  - replaces immediate WINDOW_UPDATE echoing with thresholded connection/stream receive-window replenishment
  - bounds compressed header-block buffering and request-body buffering with configured limits
  - fixes CONTINUATION handling so undefined flag bit `0x1` is no longer misinterpreted as `END_STREAM`
  - distinguishes idle-vs-closed stream handling for RST_STREAM/WINDOW_UPDATE edge cases
  - rejects client PUSH_PROMISE while still ignoring unknown extension frame types as required by HTTP/2
- `src/tigrcorn/protocols/http2/__init__.py`
  - exports the new stream-state surfaces

### Validation evidence added
- `tests/test_http2_state_machine_completion.py`
  - explicit stream lifecycle transitions
  - first-frame SETTINGS enforcement
  - concurrent-stream limit enforcement
  - strict CONTINUATION semantics without fake END_STREAM handling
  - PRIORITY self-dependency rejection
  - client PUSH_PROMISE rejection
  - thresholded WINDOW_UPDATE behavior
  - receive-window overflow rejection
  - GOAWAY monotonicity and new-stream rejection after GOAWAY
  - closed-stream WINDOW_UPDATE ignore behavior

## Repository status for these passes
- `183 passed`

## HPACK RFC 7541 correctness hardening pass

### What changed
- `src/tigrcorn/protocols/_compression.py`
  - added integer-octet, integer-value, and decoded-string length guards used by HPACK/QPACK decoders against compression-abuse inputs
  - added Huffman output-length bounding so malformed strings cannot expand without limit
- `src/tigrcorn/protocols/http2/hpack.py`
  - dynamic-table size updates are now accepted only at the legal position at the start of a header block
  - decoder now enforces configurable header-list size, header-block size, header count, string length, and integer continuation limits
  - malformed Huffman, truncated string, and oversized integer inputs now fail deterministically with `ProtocolError`
- `src/tigrcorn/protocols/http2/handler.py`
  - the live HTTP/2 path now instantiates HPACK decoding with the connection's configured header-list and header-block limits

### Validation evidence added
- `tests/test_hpack_completion_pass.py`
  - dynamic-table size updates after a header representation are rejected
  - oversized header lists and oversized header blocks are rejected
  - malformed truncation / Huffman / abusive-integer inputs are rejected
  - differential encode/decode coverage now runs against the independent third-party `hpack` library

## HTTP/1.1 RFC 9112 hardening pass

### What changed
- `src/tigrcorn/protocols/http1/parser.py`
  - validates request methods as RFC tokens
  - validates header field names and field values
  - validates chunked trailer field names and values instead of merely checking for a colon
- `src/tigrcorn/asgi/receive.py`
  - applies the same stricter header/trailer validation in streaming chunked-body receive paths
- `src/tigrcorn/protocols/http1/serializer.py`
  - added explicit response-body eligibility helpers for informational, `204`, and `304` responses
  - `103 Early Hints` reason phrase is now emitted correctly
  - response-head normalization now strips illegal body/framing headers on bodyless statuses and only auto-adds chunked framing when legal
  - whole-response serialization now suppresses bodies on bodyless statuses
- `src/tigrcorn/asgi/send.py`
  - HTTP/1.1 send path now supports multiple informational `http.response.start` events before the final response
  - final responses now suppress bodies for `1xx` / `204` / `304`
  - `HEAD` one-shot responses now preserve the payload length in `Content-Length` while still suppressing the body bytes on the wire
  - collector paths now tolerate informational responses before the final response start

### Validation evidence added
- `tests/test_http1_hardening_pass.py`
  - invalid header field names are rejected
  - invalid header field values are rejected
  - `103 Early Hints` is emitted before the final response
  - `HEAD` responses suppress the body while preserving the correct `Content-Length`
  - pipelined keep-alive traffic remains synchronized across a `204 No Content` response that would otherwise have leaked body bytes

## WebSocket RFC 7692 permessage-deflate completion pass

### What changed
- `src/tigrcorn/protocols/websocket/extensions.py`
  - added full `permessage-deflate` offer/response parsing and validation
  - added negotiated-parameter agreement objects and canonical response-header serialization
  - added context-takeover-aware compression/decompression runtime with negotiated window-bit handling
  - enforces response legality, including the rule that `client_max_window_bits` cannot appear in the response unless offered by the client
  - accepts legal server responses that request `client_no_context_takeover` even when the client only advertised bare `permessage-deflate`
- `src/tigrcorn/protocols/websocket/handler.py`
  - HTTP/1.1 WebSocket accept path now performs actual RFC 7692 negotiation instead of blindly echoing bare `permessage-deflate`
  - live text/binary send paths now use the negotiated compression runtime
  - live receive paths now correctly decompress both single-frame and fragmented compressed messages
- `src/tigrcorn/protocols/http2/websocket.py`
  - mirrored the same negotiation and runtime semantics on the HTTP/2 WebSocket path

### Validation evidence added
- `tests/test_websocket_rfc7692.py`
  - legal server-driven `client_no_context_takeover` negotiation is accepted
  - illegal `client_max_window_bits` responses without client support are rejected
  - context takeover reduces the second-message wire size under repeated payloads
  - `no_context_takeover` restarts compressor and decompressor state cleanly between messages

## Repository status for these passes
- `197 passed`

## Honest boundary

These passes complete the scoped HPACK, HTTP/1.1 hardening, and WebSocket compression work items.

They still did **not** justify an honest claim that tigrcorn was independently certified and fully RFC-complete end to end at that stage. The remaining blocker at that point was the external interoperability and certification evidence program: reproducible black-box interop matrices, packet/qlog artifacts, and release-gating against independent peers were still outstanding.

## External interoperability runner matrix pass

### What changed
- `src/tigrcorn/compat/interop_runner.py`
  - added a release-grade external interoperability runner that executes a matrix of black-box scenarios against tigrcorn
  - supports explicit matrix dimensions for protocol, role, feature, peer, cipher/group, IPv4/IPv6, Retry, resumption, `0-RTT`, key update, migration, GOAWAY, and QPACK blocking
  - added subprocess and Docker peer adapters with captured executable metadata and Docker image digest metadata
  - records deterministic evidence bundles by commit hash under `<artifact_root>/<commit_hash>/<matrix_name>/...`
  - writes `manifest.json`, `index.json`, per-scenario `scenario.json`, and per-scenario `result.json`
  - captures packet traces through deterministic TCP/UDP record proxies instead of depending on host-global sniffers
  - generates observer-side qlog output for QUIC-family scenarios from captured datagrams
  - records peer and SUT transcripts / negotiation payloads when adapters emit them through the standard environment contract
  - evaluates per-scenario RFC assertions against the observed run bundle
- `src/tigrcorn/compat/interop_cli.py`
  - added the `tigrcorn-interop` CLI entry point for running external matrices and writing artifact bundles
- `src/tigrcorn/compat/__init__.py`
  - exports the external interop runner surface
- `pyproject.toml`
  - added the `tigrcorn-interop` script entry point
- `docs/review/conformance/external_matrix.example.json`
  - added a machine-readable example matrix showing the expected schema and dimensions
- `docs/review/conformance/README.md`
  - now documents the external matrix runner, artifact layout, scenario dimensions, and usage
- `tests/fixtures_pkg/*`
  - added local fixture processes used to validate the runner implementation itself without depending on external network access

### Validation evidence added
- `tests/test_external_interop_runner_matrix.py`
  - matrix loading and dimension summarization
  - HTTP/1.1 evidence bundle generation with packet capture and transcript artifacts
  - QUIC-family observer qlog generation from captured UDP traffic
  - failed-assertion recording and result indexing
  - deterministic environment-manifest commit override behavior

## Repository status after this pass
- `202 passed`

## Honest boundary

This pass completes the **runner and evidence-bundle mechanism** required for external interoperability certification.

It does **not** by itself prove the final certification claim. That claim still depends on populating the matrix with real independent external peers, executing those scenarios in a controlled release environment, and preserving the produced evidence bundles as release artifacts.


## Independent-peer release evidence pass

### What changed
- `docs/review/conformance/external_matrix.release.json`
  - added a real independent-peer release matrix covering HTTP/1.1, HTTP/2 prior knowledge, WebSocket over HTTP/1.1, and QUIC-TLS / `h3` ALPN negotiation
- `docs/review/conformance/releases/0.3.2/release-0.3.2/...`
  - preserved a passing release artifact bundle with `manifest.json`, `index.json`, packet traces, qlog output, transcripts, negotiation payloads, and per-scenario logs
- `tests/fixtures_pkg/external_curl_client.py`
  - added a black-box `curl` adapter that records request/response transcripts and negotiated HTTP version
- `tests/fixtures_pkg/external_websocket_client.py`
  - added a black-box adapter for the independent `websockets` client
- `tests/fixtures_pkg/external_openssl_quic_client.py`
  - added an OpenSSL QUIC adapter that records certificate identity, QUIC version, ALPN, cipher suite, and verification status
- `tests/fixtures_certs/interop-localhost-cert.pem`
- `tests/fixtures_certs/interop-localhost-key.pem`
  - added deterministic localhost fixtures used by the release matrix for certificate-driven QUIC-TLS startup
- `src/tigrcorn/security/tls13/handshake.py`
  - fixed TLS certificate message emission to use DER certificate entries so independent peers can parse the handshake correctly
- `src/tigrcorn/transports/quic/connection.py`
  - fixed zero-length peer connection-ID handling so independent QUIC peers that legitimately send an empty source CID do not get rewritten into an invalid routing state
- `src/tigrcorn/compat/interop_runner.py`
  - root environment manifests now probe `curl` in addition to Git, Docker, and OpenSSL
  - source-tree hashing continues to skip generated release-artifact directories so preserved evidence bundles do not change the source hash recursively

### Validation evidence added
- `tests/test_external_independent_peer_release_matrix.py`
  - validates the committed release matrix document
  - validates the shipped release artifact bundle
  - optionally reruns the full independent-peer matrix when `curl`, OpenSSL QUIC, and `websockets` are available
- `tests/test_quic_tls_external_interop_regressions.py`
  - locks in DER certificate-entry encoding for TLS certificate messages
  - locks in zero-length QUIC peer connection-ID preservation during packet generation

## Repository status after this pass
- independent-peer release matrix: `4 / 4` passing scenarios

## Honest boundary

This pass closes the specific external interoperability evidence blocker for the covered surfaces in this archive.

It still does **not** justify an honest claim that the entire package is certifiably fully RFC-complete end to end. Remaining package-wide blockers still include:

- broader independent HTTP/3 request/response interoperability against third-party stacks
- production revocation distribution, cache management, and freshness policy beyond supplied offline evidence

## X.509 revocation lifecycle completion pass

### What changed
- `src/tigrcorn/security/x509/path.py`
  - added online OCSP acquisition from Authority Information Access URIs
  - added online CRL acquisition from CRL Distribution Point URIs
  - added a bounded in-memory revocation cache with expiry-aware eviction keyed by CRL URL and OCSP request identity
  - added freshness-policy enforcement for CRLs and OCSP responses, including clock-skew tolerance, max-validity caps, and fallback aging when OCSP `nextUpdate` is absent
  - added explicit fetch-policy controls for allowed schemes, response size limits, timeout bounds, and revocation-source toggles
- `src/tigrcorn/security/tls.py`
  - now exports the revocation cache, fetch-policy, and freshness-policy types
- `tests/test_x509_webpki_validation.py`
  - added local HTTP-backed OCSP and CRL distribution tests
  - added cache reuse validation
  - added soft-fail network-error coverage
  - added stale OCSP freshness enforcement coverage

### Validation evidence added
- `tests/test_x509_webpki_validation.py`
  - online AIA OCSP fetch succeeds and cached evidence is reused across validations
  - online CRL distribution-point fetch succeeds under required-revocation policy
  - unreachable online revocation endpoints soft-fail under `soft-fail` mode
  - stale OCSP evidence is rejected under `require` mode
  - required-mode failures surface fetch-context details for operator diagnostics

## Repository status after this pass
- online revocation acquisition, caching, and freshness policy are now built into the WebPKI validator

## Honest boundary after this pass

This closes the specific revocation-management blocker tracked earlier in the review.

It still does **not** justify an honest claim that the entire package is certifiably fully RFC-complete end to end. Remaining package-wide blockers now concentrate in the external evidence program:

- broader independent HTTP/3 request/response interoperability against third-party stacks
- broader independent HTTP/3 WebSocket interoperability against third-party stacks


## Documentation reconciliation pass

### What changed
- `README.md`
  - now explicitly states that the protocol docs and compatibility matrix are reconciled with the implemented transport surfaces
  - now names the preserved bundled evidence as the historical `0.3.2` independent-peer release bundle so the evidence path is no longer ambiguous
- `docs/protocols/http2.md`
  - now explicitly documents RFC 8441 support, HPACK dynamic state, and generic CONNECT relay support on the HTTP/2 carrier
- `docs/protocols/http3.md`
  - now explicitly documents dynamic QPACK, public certificate-driven QUIC-TLS packaging, generic CONNECT relay support, and RFC 9220 WebSocket support on the HTTP/3 carrier
- `docs/protocols/quic.md`
  - now explicitly documents the concrete handshake driver, transport-parameter negotiation, recovery/runtime integration, and public QUIC-TLS packaging
- `docs/protocols/websocket.md`
  - now explicitly documents the active RFC 8441 and RFC 9220 carriers instead of describing WebSocket as HTTP/1.1-only
- `docs/architecture/compatibility-matrix.md`
  - replaced the coarse bullet list with a real surface/evidence matrix so implemented features and shipped black-box evidence are separated cleanly
- `docs/review/conformance/README.md`
  - now describes the bundled evidence path as a preserved historical release bundle rather than implying it is the current package version's own release directory
- `tests/test_documentation_reconciliation.py`
  - added a regression guard that asserts the key protocol docs advertise the current implemented surfaces and no longer contain the earlier understatements

### Validation evidence added
- `tests/test_documentation_reconciliation.py`
  - README documents QPACK dynamic state, RFC 8441, RFC 9220, carrier-wide CONNECT relay support, and preserved release evidence
  - HTTP/3 docs no longer regress to the earlier static/literal-only QPACK description
  - WebSocket docs no longer regress to the earlier "no RFC 8441 / no HTTP/3 mapping" description
  - QUIC docs no longer regress to the earlier "no complete handshake / no recovery" description
  - compatibility and conformance docs keep the preserved `0.3.2` evidence path explicit

## Repository status after this pass
- `225 passed, 1 skipped`

## Honest boundary after this pass

This pass removes the stale and contradictory protocol-documentation descriptions that previously understated the implemented transport surface.
It does **not** broaden the independent third-party evidence program. The remaining package-level certification boundary is still the broader external HTTP/3 and HTTP/3-WebSocket interoperability bundle, not documentation drift.

## Canonical certification boundary reconciliation pass

The canonical package-wide target is now defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

That boundary no longer treats the mixed `external_matrix.current_release.json` bundle as if it were the independent certification bundle. Instead it separates:

- local conformance in `corpus.json`
- same-stack replay in `external_matrix.same_stack_replay.json`
- independent certification in `external_matrix.release.json`

The explicit package claim now includes the additional certification surfaces that were previously under-specified in the review narrative:

- RFC 9110 CONNECT semantics
- RFC 9110 trailer fields
- RFC 9110 content coding
- RFC 5280 certificate path validation
- RFC 6960 OCSP handling
- RFC 7301 ALPN negotiation
- RFC 8446 as a package-wide TLS 1.3 subsystem target rather than only a QUIC-facing subset target

## Honest boundary after the evidence-tier split

The repo is still **not** honestly certifiable end to end as a fully RFC-compliant package.

The remaining blockers are now concrete and release-gated:

- preserved third-party HTTP/3 request/response artifacts are still missing
- preserved third-party RFC 9220 WebSocket-over-HTTP/3 artifacts are still missing

The machine-readable boundary is now authoritative about evidence tiers. RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 remain intentionally bounded at `local_conformance` in the current release gate. The package-owned TCP/TLS listener-path integration for RFC 8446, RFC 5280, RFC 6960, and RFC 7301 is now present in the working tree; the outstanding certification gap has narrowed to preserved independent HTTP/3 and RFC 9220 evidence.

