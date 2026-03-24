# aioquic adapter preflight

This checkpoint executes the third-party aioquic HTTP/3 adapters directly before any strict-target artifact-promotion work proceeds.

## Exit criteria

- both adapters passed: `True`
- no peer exit code 2: `True`
- negotiation metadata emitted: `True`
- transcript metadata emitted: `True`
- ALPN h3 observed: `True`
- QUIC handshakes complete: `True`
- certificate inputs ready: `True`

## Environment snapshot

- python version: `3.13.5 (main, Jun 25 2025, 18:55:22) [GCC 14.2.0]`
- python minor version: `3.13`
- aioquic version: `1.3.0`
- wsproto version: `1.3.2`
- h2 version: `4.3.0`
- websockets version: `16.0`
- release root: `docs/review/conformance/releases/0.3.8/release-0.3.8`
- preflight bundle root: `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-aioquic-adapter-preflight-bundle`

## Scenario results

### `http3-server-aioquic-client-post`

- kind: `http3_client_adapter`
- adapter module: `tests.fixtures_third_party.aioquic_http3_client`
- peer exit code: `0`
- protocol: `h3`
- tls version: `TLSv1.3`
- server name: `localhost`
- handshake complete: `True`
- ca cert path: `tests/fixtures_certs/interop-localhost-cert.pem`
- ca cert exists: `True`
- certificate inputs ready: `True`
- packet trace emitted: `True`
- qlog emitted: `True`
- peer negotiation metadata: `http3-server-aioquic-client-post/peer_negotiation.json`
- peer transcript metadata: `http3-server-aioquic-client-post/peer_transcript.json`

### `websocket-http3-server-aioquic-client`

- kind: `http3_websocket_adapter`
- adapter module: `tests.fixtures_third_party.aioquic_http3_websocket_client`
- peer exit code: `0`
- protocol: `h3`
- tls version: `TLSv1.3`
- server name: `localhost`
- handshake complete: `True`
- ca cert path: `tests/fixtures_certs/interop-localhost-cert.pem`
- ca cert exists: `True`
- certificate inputs ready: `True`
- packet trace emitted: `True`
- qlog emitted: `True`
- peer negotiation metadata: `websocket-http3-server-aioquic-client/peer_negotiation.json`
- peer transcript metadata: `websocket-http3-server-aioquic-client/peer_transcript.json`

## Honest current repository state

- authoritative boundary after preflight: `True`
- strict target after preflight: `True`
- promotion target after preflight: `True`

This preflight closes the adapter-execution ambiguity: the aioquic HTTP/3 client and aioquic RFC 9220 WebSocket client both ran successfully and emitted negotiation metadata. It does **not** by itself promote the remaining strict-target HTTP/3 scenario artifacts into the 0.3.8 release root, so the package may still remain non-green under the stricter target until those artifacts are regenerated and assembled.
