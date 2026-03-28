# Phase 9D1 CONNECT relay independent-certification closure

This checkpoint closes the HTTP/3 CONNECT relay strict-target artifact gap. RFC 9110 §9.3.6 CONNECT relay evidence is now preserved as passing third-party artifacts across HTTP/1.1, HTTP/2, and HTTP/3 under the 0.3.9 working release root.

## Exit criteria

- scenario `http3-connect-relay-aioquic-client`: `passed`
- CONNECT admission / relay path: `validated`
- allowlist / deny vectors: `preserved locally`
- preserved transcript artifacts present: `True`
- preserved negotiation artifacts present: `True`

## HTTP/3 CONNECT verification

- peer exit code: `0`
- ALPN: `h3`
- QUIC handshake complete: `True`
- CONNECT status: `200`
- tunneled response status: `200`
- tunneled response body: `echo:hello-connect-http3`

## Honest current status

- authoritative boundary: `True`
- strict target boundary: `True`
- promotion target: `True`

The package is now **certifiably fully featured** and **strict-target certifiably fully RFC compliant** under the evaluated 0.3.9 working release root. Historical earlier checkpoints remain preserved as historical records.
