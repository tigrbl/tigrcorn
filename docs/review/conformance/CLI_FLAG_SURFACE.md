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
| App / process / development | --workers, --worker-class, --pid, --limit-max-requests, --max-requests-jitter | `process.*` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --config, --env-prefix | `app.config_file / app.env_prefix` | `pure_operator` | — | operator-only / non-RFC |
| App / process / development | --lifespan | `app.lifespan` | `pure_operator` | — | operator-only / non-RFC |
| Listener / binding | --bind, --host, --port, --uds, --fd, --endpoint, --insecure-bind, --quic-bind, --transport, --reuse-port, --reuse-address, --backlog | `listeners[]` | `hybrid` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001 | non-RFC values: --transport pipe, --transport inproc |
| TLS / security | --ssl-certfile, --ssl-keyfile, --ssl-ca-certs, --ssl-require-client-cert, --ssl-ciphers, --ssl-alpn, --ssl-ocsp-mode, --ssl-ocsp-soft-fail, --ssl-ocsp-cache-size, --ssl-ocsp-max-age, --ssl-crl-mode, --ssl-revocation-fetch | `tls.*` | `rfc_scoped` | RFC 8446, RFC 5280, RFC 6960, RFC 7301 | — |
| TLS / security | --proxy-headers, --forwarded-allow-ips, --root-path, --server-header, --no-server-header | `proxy.*` | `pure_operator` | — | operator-only / non-RFC |
| Logging / observability | --log-level, --access-log, --no-access-log, --access-log-file, --access-log-format, --error-log-file, --log-config, --structured-log, --metrics, --metrics-bind, --statsd-host, --otel-endpoint | `logging.* / metrics.*` | `pure_operator` | — | operator-only / non-RFC |
| Resource / timeouts / concurrency | --timeout-keep-alive, --read-timeout, --write-timeout, --timeout-graceful-shutdown, --limit-concurrency, --max-connections, --max-tasks, --max-streams, --max-body-size, --max-header-size, --websocket-max-message-size, --websocket-ping-interval, --websocket-ping-timeout, --idle-timeout | `http.* / websocket.* / scheduler.*` | `hybrid` | RFC 9110, RFC 9112, RFC 9113, RFC 9114, RFC 6455, RFC 8441, RFC 9220 | — |
| Protocol / transport | --http, --protocol, --disable-websocket, --disable-h2c, --websocket-compression, --connect-policy, --connect-allow, --trailer-policy, --content-coding-policy, --content-codings, --quic-require-retry, --quic-max-datagram-size, --quic-idle-timeout, --quic-early-data-policy, --pipe-mode | `http.* / websocket.* / quic.* / listeners[].protocols` | `rfc_scoped` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8 | non-RFC values: --pipe-mode, --protocol rawframed, --protocol custom |

## Hidden experimental flag

`--quic-secret` remains supported for backward-compatible local experimentation, but it is intentionally omitted from the public certified CLI surface.
