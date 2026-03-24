# Deployment profiles

This document defines the finite deployment-profile model used to avoid a literal Cartesian product of all flags.

| Profile ID | Claim class | RFC target(s) | Description |
|---|---|---|---|
| `http1_baseline` | `rfc_scoped` | RFC 9112 | Single-listener HTTP/1.1 baseline profile. |
| `http1_proxy` | `hybrid` | RFC 9112 | HTTP/1.1 behind a reverse proxy with trusted forwarded headers. |
| `http2_cleartext` | `rfc_scoped` | RFC 9113 | HTTP/2 cleartext / h2c profile. |
| `http2_tls` | `rfc_scoped` | RFC 9113, RFC 8446, RFC 7301 | HTTP/2 over TLS with ALPN. |
| `http3_quic` | `rfc_scoped` | RFC 9000, RFC 9001, RFC 9002, RFC 9114 | HTTP/3 over QUIC. |
| `http3_quic_mtls` | `rfc_scoped` | RFC 9000, RFC 9001, RFC 9114, RFC 8446, RFC 5280 | HTTP/3 over QUIC with client-certificate verification. |
| `websocket_http11` | `rfc_scoped` | RFC 6455 | WebSocket over HTTP/1.1. |
| `websocket_http11_permessage_deflate` | `rfc_scoped` | RFC 6455, RFC 7692 | WebSocket over HTTP/1.1 with permessage-deflate. |
| `websocket_http2` | `rfc_scoped` | RFC 8441 | WebSocket over HTTP/2 extended CONNECT. |
| `websocket_http2_permessage_deflate` | `rfc_scoped` | RFC 8441, RFC 7692 | WebSocket over HTTP/2 with permessage-deflate. |
| `websocket_http3` | `rfc_scoped` | RFC 9220 | WebSocket over HTTP/3 extended CONNECT. |
| `websocket_http3_permessage_deflate` | `rfc_scoped` | RFC 9220, RFC 7692 | WebSocket over HTTP/3 with permessage-deflate. |
| `connect_http11` | `rfc_scoped` | RFC 9110 §9.3.6, RFC 9112 | CONNECT relay over HTTP/1.1. |
| `connect_http2` | `rfc_scoped` | RFC 9110 §9.3.6, RFC 9113 | CONNECT relay over HTTP/2. |
| `connect_http3` | `rfc_scoped` | RFC 9110 §9.3.6, RFC 9114 | CONNECT relay over HTTP/3. |
| `trailers_http11` | `rfc_scoped` | RFC 9110 §6.5, RFC 9112 | Trailers over HTTP/1.1. |
| `trailers_http2` | `rfc_scoped` | RFC 9110 §6.5, RFC 9113 | Trailers over HTTP/2. |
| `trailers_http3` | `rfc_scoped` | RFC 9110 §6.5, RFC 9114 | Trailers over HTTP/3. |
| `content_coding_http11` | `rfc_scoped` | RFC 9110 §8, RFC 9112 | Content coding over HTTP/1.1. |
| `content_coding_http2` | `rfc_scoped` | RFC 9110 §8, RFC 9113 | Content coding over HTTP/2. |
| `content_coding_http3` | `rfc_scoped` | RFC 9110 §8, RFC 9114 | Content coding over HTTP/3. |
| `tls_ocsp_strict` | `rfc_scoped` | RFC 8446, RFC 5280, RFC 6960 | TLS listener with strict OCSP policy. |
| `worker_prefork_proxy` | `pure_operator` | — | Worker-prefork deployment behind a proxy. |
| `unix_socket_proxy` | `pure_operator` | — | Unix-socket deployment behind a reverse proxy. |
| `fd_inherited_worker` | `pure_operator` | — | FD-inherited listener with worker supervision. |
| `custom_pipe_rawframed` | `non_rfc_custom` | — | Pipe/rawframed custom transport outside the strict RFC-certified surface. |
