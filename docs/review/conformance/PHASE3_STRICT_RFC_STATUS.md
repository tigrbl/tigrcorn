# Phase 3 strict RFC status

This checkpoint lands the public RFC-scoped policy surface and runtime wiring for the strict RFC gap set.

## Green today

- authoritative canonical boundary
- authoritative release-gate evaluator
- local conformance and runtime coverage for the newly public strict-RFC flag surfaces

## Landed public RFC-scoped controls

- `--websocket-compression {off,permessage-deflate}`
- `--connect-policy {deny,relay,allowlist}`
- `--connect-allow ...`
- `--trailer-policy {drop,pass,strict}`
- `--content-coding-policy {identity-only,allowlist,strict}`
- `--content-codings ...`
- `--ssl-ocsp-mode {off,soft-fail,require}`
- `--ssl-ocsp-cache-size`
- `--ssl-ocsp-max-age`
- `--ssl-crl-mode {off,soft-fail,require}`
- `--ssl-revocation-fetch {off,on}`
- `--ssl-alpn ...`

## Honest remaining blockers for the stricter overlay

The stricter all-surfaces-independent overlay still requires preserved independent artifacts for:

- `websocket-http11-server-websockets-client-permessage-deflate`
- `websocket-http2-server-h2-client-permessage-deflate`
- `websocket-http3-server-aioquic-client-permessage-deflate`
- `http11-connect-relay-curl-client`
- `http2-connect-relay-h2-client`
- `http3-connect-relay-aioquic-client`
- `http11-trailer-fields-curl-client`
- `http2-trailer-fields-h2-client`
- `http3-trailer-fields-aioquic-client`
- `http11-content-coding-curl-client`
- `http2-content-coding-curl-client`
- `http3-content-coding-aioquic-client`
- `tls-server-ocsp-validation-openssl-client`

That means this checkpoint is a **strict-RFC public-surface and runtime closure checkpoint**, not yet a full strict-overlay certification closure checkpoint.
