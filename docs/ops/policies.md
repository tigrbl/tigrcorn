# Policy Surface

This file is generated from the shared Phase 3 policy metadata, current parser help, and runtime default audit.

## Proxy Trust

- Claim: `TC-CONTRACT-PROXY-TRUST`
- Category: `Proxy contract`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3, WebSocket`
- Description: Trusted proxy admission is explicit and fail-closed.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--proxy-headers` | `proxy.proxy_headers` | `False` | Trust Forwarded and X-Forwarded-* identity headers from allowed peers |
| `--forwarded-allow-ips` | `proxy.forwarded_allow_ips` | `[]` | Trusted proxy peers for Forwarded and X-Forwarded-* processing; repeat or use comma-separated values |

## Proxy Precedence

- Claim: `TC-CONTRACT-PROXY-PRECEDENCE`
- Category: `Proxy contract`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3, WebSocket`
- Description: Forwarded and X-Forwarded-* precedence is explicit for client, scheme, host, and root_path.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--proxy-headers` | `proxy.proxy_headers` | `False` | Trust Forwarded and X-Forwarded-* identity headers from allowed peers |
| `--forwarded-allow-ips` | `proxy.forwarded_allow_ips` | `[]` | Trusted proxy peers for Forwarded and X-Forwarded-* processing; repeat or use comma-separated values |
| `--root-path` | `proxy.root_path` | `` | Base ASGI root_path applied before trusted proxy prefix normalization |

## Proxy Normalization

- Claim: `TC-CONTRACT-PROXY-NORMALIZATION`
- Category: `Proxy contract`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3, WebSocket`
- Description: Root-path and forwarded-header normalization is frozen and shared across HTTP and WebSocket scope building.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--root-path` | `proxy.root_path` | `` | Base ASGI root_path applied before trusted proxy prefix normalization |

## CONNECT Policy

- Claim: `TC-POLICY-CONNECT`
- Category: `RFC policy`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3`
- Description: CONNECT relay admission is explicit as deny, relay, or allowlist.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--connect-policy` | `http.connect_policy` | `deny` | CONNECT relay policy: deny, relay, or allowlist |
| `--connect-allow` | `http.connect_allow` | `[]` | Allowed CONNECT authorities or CIDR targets when CONNECT policy is allowlist |

## Trailer Policy

- Claim: `TC-POLICY-TRAILERS`
- Category: `RFC policy`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3`
- Description: Trailer acceptance and forwarding posture is explicit across supported carriers.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--trailer-policy` | `http.trailer_policy` | `pass` | Trailer handling policy across supported HTTP/1.1, HTTP/2, and HTTP/3 carriers |

## Content-Coding Policy

- Claim: `TC-POLICY-CONTENT-CODING`
- Category: `RFC policy`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3`
- Description: Response content-coding policy and the supported coding allowlist are explicit.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--content-coding-policy` | `http.content_coding_policy` | `allowlist` | Response content-coding policy: allowlist, identity-only, or strict |
| `--content-codings` | `http.content_codings` | `None` | Supported response codings for allowlist/strict policy; repeat or use comma-separated values |

## H2C Policy

- Claim: `TC-POLICY-H2C`
- Category: `Protocol policy`
- Carriers: `HTTP/1.1, HTTP/2`
- Description: Cleartext HTTP/2 upgrade and preface detection is explicit rather than implicit.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--disable-h2c` | `http.enable_h2c` | `False` | Disable cleartext HTTP/2 upgrade and direct-preface detection on eligible listeners |

## ALPN Policy

- Claim: `TC-POLICY-ALPN`
- Category: `TLS policy`
- Carriers: `TLS over HTTP/1.1, TLS over HTTP/2, QUIC/HTTP/3`
- Description: ALPN offer ordering and negotiation posture is a stable public control.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--ssl-alpn` | `tls.alpn_protocols` | `None` | ALPN offer list; repeat or use comma-separated values |

## OCSP and Revocation Policy

- Claim: `TC-POLICY-REVOCATION`
- Category: `TLS policy`
- Carriers: `TLS over HTTP/1.1, TLS over HTTP/2, QUIC/HTTP/3`
- Description: OCSP, CRL, and remote revocation-fetch policy is explicit and operator-visible.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--ssl-ocsp-mode` | `tls.ocsp_mode` | `off` | OCSP revocation mode for peer-certificate validation |
| `--ssl-ocsp-soft-fail` | `tls.ocsp_soft_fail` | `False` | Allow OCSP-unavailable validation to continue when strict mode is not required |
| `--ssl-ocsp-cache-size` | `tls.ocsp_cache_size` | `128` | Maximum cached OCSP responses kept in the revocation cache |
| `--ssl-ocsp-max-age` | `tls.ocsp_max_age` | `43200.0` | Maximum acceptable OCSP response age in seconds |
| `--ssl-crl-mode` | `tls.crl_mode` | `off` | CRL validation mode for peer-certificate revocation checks |
| `--ssl-crl` | `tls.crl` | `None` | Local CRL file loaded into the package-owned revocation material set |
| `--ssl-revocation-fetch` | `tls.revocation_fetch` | `True` | Enable or disable online revocation fetching for OCSP/CRL validation |

## WebSocket Compression Policy

- Claim: `TC-POLICY-WEBSOCKET-COMPRESSION`
- Category: `WebSocket policy`
- Carriers: `WebSocket over HTTP/1.1, WebSocket over HTTP/2, WebSocket over HTTP/3`
- Description: permessage-deflate policy is explicit across supported WebSocket carriers.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--websocket-compression` | `websocket.compression` | `off` | WebSocket compression policy across the supported H1, H2, and H3 carriers |

## Limits and Timeouts

- Claim: `TC-POLICY-LIMITS-TIMEOUTS`
- Category: `Runtime policy`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3, WebSocket`
- Description: Resource, buffering, and timeout posture is a reviewed public operator contract.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--timeout-keep-alive` | `http.keep_alive_timeout` | `5.0` | Idle keep-alive timeout in seconds before an inactive connection is closed |
| `--read-timeout` | `http.read_timeout` | `30.0` | Maximum request read time in seconds for package-owned transports |
| `--write-timeout` | `http.write_timeout` | `30.0` | Maximum response write time in seconds for package-owned transports |
| `--timeout-graceful-shutdown` | `http.shutdown_timeout` | `30.0` | Graceful-drain timeout in seconds before shutdown stops waiting on active work |
| `--max-connections` | `scheduler.max_connections` | `None` | Maximum simultaneously open client connections |
| `--max-tasks` | `scheduler.max_tasks` | `None` | Maximum concurrently scheduled background work tasks |
| `--max-streams` | `scheduler.max_streams` | `None` | Maximum concurrently admitted logical streams or units of work per session policy |
| `--max-body-size` | `http.max_body_size` | `16777216` | Maximum accepted request body size in bytes |
| `--max-header-size` | `http.max_header_size` | `65536` | Maximum accepted request-header bytes before rejection |
| `--http1-max-incomplete-event-size` | `http.http1_max_incomplete_event_size` | `65536` | Maximum buffered incomplete HTTP/1.1 request-head bytes before rejection |
| `--http1-buffer-size` | `http.http1_buffer_size` | `65536` | HTTP/1.1 incremental read buffer size in bytes |
| `--http1-header-read-timeout` | `http.http1_header_read_timeout` | `None` | HTTP/1.1 request-head read timeout in seconds |
| `--http1-keep-alive` | `http.http1_keep_alive` | `True` | Enable HTTP/1.1 connection persistence |
| `--no-http1-keep-alive` | `http.http1_keep_alive` | `True` | Disable enable http/1.1 connection persistence |
| `--http2-max-concurrent-streams` | `http.http2_max_concurrent_streams` | `128` | Advertised HTTP/2 MAX_CONCURRENT_STREAMS value for peer-created streams |
| `--http2-max-headers-size` | `http.http2_max_headers_size` | `65536` | HTTP/2-specific decoded header-list size cap |
| `--http2-max-frame-size` | `http.http2_max_frame_size` | `16384` | Advertised HTTP/2 MAX_FRAME_SIZE for inbound peer frames |
| `--http2-adaptive-window` | `http.http2_adaptive_window` | `False` | Enable adaptive HTTP/2 receive-window growth |
| `--no-http2-adaptive-window` | `http.http2_adaptive_window` | `False` | Disable enable adaptive http/2 receive-window growth |
| `--http2-initial-connection-window-size` | `http.http2_initial_connection_window_size` | `65535` | HTTP/2 connection-level receive window target |
| `--http2-initial-stream-window-size` | `http.http2_initial_stream_window_size` | `65535` | Advertised HTTP/2 INITIAL_WINDOW_SIZE for peer-created streams |
| `--http2-keep-alive-interval` | `http.http2_keep_alive_interval` | `None` | Idle interval before sending an HTTP/2 connection-level PING |
| `--http2-keep-alive-timeout` | `http.http2_keep_alive_timeout` | `None` | Timeout in seconds for an HTTP/2 keep-alive PING acknowledgement |
| `--websocket-max-message-size` | `websocket.max_message_size` | `16777216` | Maximum accepted WebSocket message size in bytes |
| `--websocket-max-queue` | `websocket.max_queue` | `32` | Maximum queued inbound WebSocket messages before transport backpressure applies |
| `--idle-timeout` | `http.idle_timeout` | `30.0` | Idle application/session timeout in seconds |

## WebSocket Heartbeat

- Claim: `TC-POLICY-WEBSOCKET-HEARTBEAT`
- Category: `WebSocket policy`
- Carriers: `WebSocket over HTTP/1.1, WebSocket over HTTP/2, WebSocket over HTTP/3`
- Description: Heartbeat interval and timeout are explicit and carrier-parity tested.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--websocket-ping-interval` | `websocket.ping_interval` | `None` | Outbound WebSocket heartbeat interval in seconds |
| `--websocket-ping-timeout` | `websocket.ping_timeout` | `None` | WebSocket heartbeat acknowledgement timeout in seconds |

## Drain and Admission Control

- Claim: `TC-POLICY-DRAIN-ADMISSION`
- Category: `Runtime policy`
- Carriers: `HTTP/1.1, HTTP/2, HTTP/3, WebSocket`
- Description: Request, stream, and shutdown admission posture is explicit instead of hidden behind scheduler internals.

| Flag | Config path | Effective default | Help |
|---|---|---|---|
| `--limit-concurrency` | `scheduler.limit_concurrency` | `None` | Maximum concurrently admitted request/stream work across the production scheduler |
| `--max-connections` | `scheduler.max_connections` | `None` | Maximum simultaneously open client connections |
| `--max-tasks` | `scheduler.max_tasks` | `None` | Maximum concurrently scheduled background work tasks |
| `--max-streams` | `scheduler.max_streams` | `None` | Maximum concurrently admitted logical streams or units of work per session policy |
| `--timeout-graceful-shutdown` | `http.shutdown_timeout` | `30.0` | Graceful-drain timeout in seconds before shutdown stops waiting on active work |

