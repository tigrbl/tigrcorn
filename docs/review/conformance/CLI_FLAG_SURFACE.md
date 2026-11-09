# CLI flag surface

This document freezes the public CLI taxonomy for the current config / CLI substrate checkpoint.

Legend:

- `rfc_scoped` — directly exposes or gates an RFC-governed surface
- `hybrid` — operational / defensive control that can affect RFC behavior under stress
- `pure_operator` — operator-only surface outside the RFC boundary
- `non_rfc_custom` — custom / experimental surface intentionally excluded from strict RFC certification

The machine-readable source of truth is `cli_flag_surface.json`.

| Family | Flags | Config path | Claim class | RFC target(s) | Notes |
|---|---|---|---|---|---|
| App / process / development | --factory | `app.factory` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --app-dir | `app.app_dir` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --reload, --reload-dir, --reload-include, --reload-exclude | `app.reload*` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --workers, --worker-class, --pid, --limit-max-requests, --max-requests-jitter, --runtime, --worker-healthcheck-timeout | `process.*` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --config, --env-prefix, --env-file | `app.config_file / app.env_prefix` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --lifespan | `app.lifespan` | `pure_operator` | — | operator-only / non-RFC |
| Listener / binding | --bind, --host, --port, --uds, --fd, --endpoint, --insecure-bind, --quic-bind, --transport, --reuse-port, --reuse-address, --backlog, --user, --group, --umask | `listeners[]` | `hybrid` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001 | non-RFC values: --transport pipe, --transport inproc |
| Static / delivery | --static-path-route, --static-path-mount, --static-path-dir-to-file, --no-static-path-dir-to-file, --static-path-index-file, --static-path-expires | `static.*` | `pure_operator` | — | server-native static route / mount / index / expires operator surface |
| TLS / security | --ssl-certfile, --ssl-keyfile, --ssl-keyfile-password, --ssl-ca-certs, --ssl-require-client-cert, --ssl-ciphers, --ssl-alpn, --ssl-ocsp-mode, --ssl-ocsp-soft-fail, --ssl-ocsp-cache-size, --ssl-ocsp-max-age, --ssl-crl-mode, --ssl-crl, --ssl-revocation-fetch | `tls.*` | `rfc_scoped` | RFC 8446, RFC 5280, RFC 6960, RFC 7301 | includes encrypted private-key password input and direct local CRL material loading while preserving existing OCSP/CRL policy controls |
| TLS / security | --proxy-headers, --forwarded-allow-ips, --root-path, --server-header, --no-server-header, --date-header, --no-date-header, --header, --server-name | `proxy.*` | `pure_operator` | — | operator-only / non-RFC |
| Logging / observability | --log-level, --access-log, --no-access-log, --access-log-file, --access-log-format, --error-log-file, --log-config, --structured-log, --metrics, --metrics-bind, --statsd-host, --otel-endpoint, --use-colors, --no-use-colors | `logging.* / metrics.*` | `pure_operator` | — | operator-only / non-RFC |
| Resource / timeouts / concurrency | --timeout-keep-alive, --read-timeout, --write-timeout, --timeout-graceful-shutdown, --limit-concurrency, --max-connections, --max-tasks, --max-streams, --max-body-size, --max-header-size, --http1-max-incomplete-event-size, --http1-buffer-size, --http1-header-read-timeout, --http1-keep-alive, --no-http1-keep-alive, --http2-max-concurrent-streams, --http2-max-headers-size, --http2-max-frame-size, --http2-adaptive-window, --no-http2-adaptive-window, --http2-initial-connection-window-size, --http2-initial-stream-window-size, --http2-keep-alive-interval, --http2-keep-alive-timeout, --websocket-max-message-size, --websocket-max-queue, --websocket-ping-interval, --websocket-ping-timeout, --idle-timeout | `http.* / websocket.* / scheduler.*` | `hybrid` | RFC 9110, RFC 9112, RFC 9113, RFC 9114, RFC 6455, RFC 8441, RFC 9220 | includes protocol-specific H1 budgeting, explicit H2 SETTINGS/flow-control/keepalive controls, and WebSocket inbound-queue controls |
| Protocol / transport | --http, --protocol, --disable-websocket, --disable-h2c, --websocket-compression, --connect-policy, --connect-allow, --trailer-policy, --content-coding-policy, --content-codings, --alt-svc, --alt-svc-auto, --no-alt-svc-auto, --alt-svc-ma, --alt-svc-persist, --quic-require-retry, --quic-max-datagram-size, --quic-idle-timeout, --quic-early-data-policy, --webtransport-max-sessions, --webtransport-max-streams, --webtransport-max-datagram-size, --webtransport-origin, --webtransport-path, --pipe-mode | `http.* / websocket.* / quic.* / webtransport.* / listeners[].protocols` | `rfc_scoped` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8 | non-RFC values: --pipe-mode, --protocol rawframed, --protocol custom; WebTransport is enabled through --protocol webtransport and tuned with webtransport.* controls |

## Hidden experimental flag

`--quic-secret` remains supported for backward-compatible local experimentation, but it is intentionally omitted from the public certified CLI surface.
