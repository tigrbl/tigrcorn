# CLI operator reference

This page is the human operator reference for Tigrcorn's public CLI surfaces. It complements, and does not replace, the canonical current-state and conformance material.

Canonical supporting sources:

- `README.md`
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/DEPLOYMENT_PROFILES.md`
- `docs/review/conformance/cli_help.current.txt`
- `docs/review/conformance/tigrcorn_interop_help.current.txt`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`

## Table of contents

- [Command surfaces](#command-surfaces)
- [Config precedence and source merging](#config-precedence-and-source-merging)
- [Common launch recipes](#common-launch-recipes)
- [Deployment profiles](#deployment-profiles)
- [Flag families at a glance](#flag-families-at-a-glance)
- [Exhaustive public flag reference](#exhaustive-public-flag-reference)
- [Help snapshots](#help-snapshots)
- [Notes on hidden or non-public flags](#notes-on-hidden-or-non-public-flags)

## Command surfaces

| Command | Role | Primary audience | Notes |
|---|---|---|---|
| `tigrcorn` | main server launcher | operators, developers, CI | Loads an ASGI target, binds listeners, and exposes the full public flag surface. |
| `python -m tigrcorn` | equivalent module entrypoint | operators, developers, CI | Useful when invoking from an interpreter-managed environment. |
| `tigrcorn-interop` | external interoperability runner | maintainers, release owners, auditors | Executes preserved scenario matrices and writes evidence bundles. |

## Config precedence and source merging

Tigrcorn's public precedence contract is:

```text
CLI > env > config file > defaults
```

Public config-loading surfaces:

- `--config`, `--env-file`, and `--env-prefix` on the CLI
- `tigrcorn.config.load_config_file`
- `tigrcorn.config.load_env_config`
- `tigrcorn.config.build_config_from_sources`

Use this model whenever you document or debug configuration behavior. The CLI is allowed to override everything else; defaults are the last resort.

## Common launch recipes

### Minimal HTTP/1.1 + HTTP/2 launch

```bash
tigrcorn examples.echo_http.app:app --host 127.0.0.1 --port 8000
```

### App factory launch

```bash
tigrcorn examples.echo_http.app:create_app --factory --host 127.0.0.1 --port 8000
```

### Explicit config file + env file + env prefix

```bash
tigrcorn examples.echo_http.app:app \
  --config ./tigrcorn.toml \
  --env-file ./.env \
  --env-prefix TIGRCORN
```

### HTTP/2 over TLS

```bash
tigrcorn examples.echo_http.app:app \
  --bind 127.0.0.1:8443 \
  --http 2 \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key
```

### HTTP/3 / QUIC over UDP

```bash
tigrcorn examples.echo_http.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --protocol http3 \
  --protocol quic \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key
```

### HTTP/3 / QUIC with client-certificate verification

```bash
tigrcorn examples.echo_http.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --protocol http3 \
  --protocol quic \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key \
  --ssl-ca-certs ./certs/ca.pem \
  --ssl-require-client-cert
```

### HTTP/1.1 and WebSocket echo

```bash
tigrcorn examples.websocket_echo.app:app \
  --host 127.0.0.1 \
  --port 9000 \
  --http 1.1
```

### WebSocket permessage-deflate

```bash
tigrcorn examples.websocket_echo.app:app \
  --host 127.0.0.1 \
  --port 9000 \
  --websocket-compression permessage-deflate
```

### Static route with cache headers

```bash
tigrcorn examples.http_entity_static.app:app \
  --static-path-route /assets \
  --static-path-mount ./public \
  --static-path-dir-to-file \
  --static-path-index-file index.html \
  --static-path-expires 3600
```

### CONNECT, trailer, and content-coding policies

```bash
tigrcorn examples.echo_http.app:app \
  --connect-policy allowlist \
  --connect-allow 127.0.0.1:5432 \
  --trailer-policy strict \
  --content-coding-policy allowlist \
  --content-codings br,gzip,deflate
```

### Automatic Alt-Svc advertisement

```bash
tigrcorn examples.advanced_protocol_delivery.alt_svc_app:app \
  --bind 127.0.0.1:8080 \
  --quic-bind 127.0.0.1:8443 \
  --http 1.1 --http 2 --http 3 \
  --alt-svc-auto \
  --alt-svc-ma 86400 \
  --alt-svc-persist
```

### Metrics, log files, and structured logging

```bash
tigrcorn examples.echo_http.app:app \
  --log-level info \
  --structured-log \
  --access-log-file ./logs/access.log \
  --error-log-file ./logs/error.log \
  --metrics \
  --metrics-bind 127.0.0.1:9100 \
  --statsd-host 127.0.0.1:8125 \
  --otel-endpoint http://127.0.0.1:4318
```

### Runtime selection, reload, and worker supervision

```bash
tigrcorn examples.echo_http.app:app \
  --workers 4 \
  --runtime auto \
  --reload \
  --reload-dir ./src \
  --reload-include '*.py' \
  --reload-exclude '*.tmp' \
  --limit-max-requests 10000 \
  --max-requests-jitter 500
```

### Unix domain socket and ownership controls

```bash
tigrcorn examples.echo_http.app:app \
  --transport unix \
  --uds /tmp/tigrcorn.sock \
  --user www-data \
  --group www-data \
  --umask 18
```

### Pipe / custom operator transports

```bash
tigrcorn examples.echo_http.app:app \
  --transport pipe \
  --pipe-mode rawframed \
  --protocol rawframed
```

```bash
tigrcorn examples.echo_http.app:app \
  --transport inproc \
  --protocol custom
```

These operator transports are part of the public operator surface but sit outside the strict RFC claim where the boundary docs say so.

### External interoperability matrix execution

```bash
tigrcorn-interop \
  --matrix docs/review/conformance/external_matrix.release.json \
  --output ./artifacts/interop
```

```bash
tigrcorn-interop \
  --matrix docs/review/conformance/external_matrix.current_release.json \
  --output ./artifacts/current-release \
  --strict
```

```bash
tigrcorn-interop \
  --matrix docs/review/conformance/external_matrix.same_stack_replay.json \
  --output ./artifacts/same-stack \
  --only websocket-http3-server-aioquic-client
```

## Deployment profiles

The deployment profiles are the normalized, machine-readable public profile map for the CLI and operator surface.

| Profile | Claim class | RFC targets | Description |
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


## Flag families at a glance

| Family | Flag groups | Public flag strings |
|---|---:|---:|
| `App / process / development` | 6 | 17 |
| `Listener / binding` | 1 | 15 |
| `Logging / observability` | 1 | 14 |
| `Protocol / transport` | 1 | 20 |
| `Resource / timeouts / concurrency` | 1 | 29 |
| `Static / delivery` | 1 | 6 |
| `TLS / security` | 2 | 23 |


## Exhaustive public flag reference

The rows below mirror the current public flag truth in `docs/review/conformance/cli_flag_surface.json`.

## App / process / development

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `factory` | `--factory` | `app.factory` | `pure_operator` | — |
| `app_dir` | `--app-dir` | `app.app_dir` | `pure_operator` | — |
| `reload` | `--reload`, `--reload-dir`, `--reload-include`, `--reload-exclude` | `app.reload*` | `pure_operator` | — |
| `workers` | `--workers`, `--worker-class`, `--pid`, `--limit-max-requests`, `--max-requests-jitter`, `--runtime`, `--worker-healthcheck-timeout` | `process.*` | `pure_operator` | — |
| `config_source` | `--config`, `--env-prefix`, `--env-file` | `app.config_file / app.env_prefix` | `pure_operator` | — |
| `lifespan` | `--lifespan` | `app.lifespan` | `pure_operator` | — |

### `factory`

| Field | Value |
|---|---|
| Flags | `--factory` |
| Family | `App / process / development` |
| Config path | `app.factory` |
| Claim class | `pure_operator` |
| Default | `False` |
| RFC targets | — |
| Validation rules | `boolean` |
| Deployment profiles | `http1_baseline` |
| Unit tests | `tests/test_cli_and_asgi3.py::CLIAndASGI3Tests::test_parser` |
| Interop scenarios | — |
| Performance profiles | — |

### `app_dir`

| Field | Value |
|---|---|
| Flags | `--app-dir` |
| Family | `App / process / development` |
| Config path | `app.app_dir` |
| Claim class | `pure_operator` |
| Default | `None` (loads from current working directory when unset) |
| RFC targets | — |
| Validation rules | `path string` |
| Deployment profiles | `http1_baseline` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_app_dir_round_trip` |
| Interop scenarios | — |
| Performance profiles | — |

### `reload`

| Field | Value |
|---|---|
| Flags | `--reload`, `--reload-dir`, `--reload-include`, `--reload-exclude` |
| Family | `App / process / development` |
| Config path | `app.reload*` |
| Claim class | `pure_operator` |
| Default | `False` |
| RFC targets | — |
| Validation rules | `boolean + repeatable globs/paths` |
| Deployment profiles | `worker_prefork_proxy` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_parser_accepts_grouped_phase2_flags` |
| Interop scenarios | — |
| Performance profiles | — |

### `workers`

| Field | Value |
|---|---|
| Flags | `--workers`, `--worker-class`, `--pid`, `--limit-max-requests`, `--max-requests-jitter`, `--runtime`, `--worker-healthcheck-timeout` |
| Family | `App / process / development` |
| Config path | `process.*` |
| Claim class | `pure_operator` |
| Default | `None` |
| RFC targets | — |
| Validation rules | `workers positive integer`, `worker_class in supported set`, `runtime in {auto, asyncio, uvloop}`, `healthcheck timeout positive float` |
| Deployment profiles | `worker_prefork_proxy`, `fd_inherited_worker` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_parser_accepts_grouped_phase2_flags` |
| Interop scenarios | — |
| Performance profiles | `worker_scale` |

### `config_source`

| Field | Value |
|---|---|
| Flags | `--config`, `--env-prefix`, `--env-file` |
| Family | `App / process / development` |
| Config path | `app.config_file / app.env_prefix` |
| Claim class | `pure_operator` |
| Default | `None` |
| RFC targets | — |
| Validation rules | `config file path`, `env prefix string`, `optional env-file bootstrap` |
| Deployment profiles | `http1_baseline` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_config_source_precedence_cli_over_env_over_file` |
| Interop scenarios | — |
| Performance profiles | — |

### `lifespan`

| Field | Value |
|---|---|
| Flags | `--lifespan` |
| Family | `App / process / development` |
| Config path | `app.lifespan` |
| Claim class | `pure_operator` |
| Default | `auto` |
| RFC targets | — |
| Validation rules | `one of auto,on,off` |
| Deployment profiles | `http1_baseline` |
| Unit tests | `tests/test_config_matrix.py::ConfigMatrixTests::test_tcp_defaults` |
| Interop scenarios | — |
| Performance profiles | — |


## Listener / binding

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `binds` | `--bind`, `--host`, `--port`, `--uds`, `--fd`, `--endpoint`, `--insecure-bind`, `--quic-bind`, `--transport`, `--reuse-port`, `--reuse-address`, `--backlog`, `--user`, `--group`, `--umask` | `listeners[]` | `hybrid` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001 |

### `binds`

| Field | Value |
|---|---|
| Flags | `--bind`, `--host`, `--port`, `--uds`, `--fd`, `--endpoint`, `--insecure-bind`, `--quic-bind`, `--transport`, `--reuse-port`, `--reuse-address`, `--backlog`, `--user`, `--group`, `--umask` |
| Family | `Listener / binding` |
| Config path | `listeners[]` |
| Claim class | `hybrid` |
| Default | `defaults file` |
| RFC targets | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001 |
| Validation rules | `listener kinds validated`, `ports in range`, `paths/FDs typed`, `unix socket ownership controls only apply to unix listeners` |
| Deployment profiles | `http1_baseline`, `http2_tls`, `http3_quic`, `fd_inherited_worker`, `unix_socket_proxy`, `custom_pipe_rawframed` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_build_config_from_namespace_maps_nested_submodels` |
| Interop scenarios | — |
| Performance profiles | `http1_baseline`, `http3_clean` |


## Static / delivery

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `static_path` | `--static-path-route`, `--static-path-mount`, `--static-path-dir-to-file`, `--no-static-path-dir-to-file`, `--static-path-index-file`, `--static-path-expires` | `static.*` | `pure_operator` | — |

### `static_path`

| Field | Value |
|---|---|
| Flags | `--static-path-route`, `--static-path-mount`, `--static-path-dir-to-file`, `--no-static-path-dir-to-file`, `--static-path-index-file`, `--static-path-expires` |
| Family | `Static / delivery` |
| Config path | `static.*` |
| Claim class | `pure_operator` |
| Default | `{'route': None, 'mount': None, 'dir_to_file': True, 'index_file': 'index.html', 'expires': None}` |
| RFC targets | — |
| Validation rules | `route string`, `path string`, `boolean toggle`, `string or null`, `non-negative integer or null` |
| Deployment profiles | `http1_baseline`, `http2_tls`, `http3_quic` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_parser_accepts_grouped_phase2_flags`, `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_build_config_from_namespace_maps_nested_submodels`, `tests/test_phase2_static_delivery_surface.py::StaticAndPathsendSurfaceTests::test_cli_main_allows_static_only_mount_without_app_import_string` |
| Interop scenarios | — |
| Performance profiles | — |


## TLS / security

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `tls` | `--ssl-certfile`, `--ssl-keyfile`, `--ssl-keyfile-password`, `--ssl-ca-certs`, `--ssl-require-client-cert`, `--ssl-ciphers`, `--ssl-alpn`, `--ssl-ocsp-mode`, `--ssl-ocsp-soft-fail`, `--ssl-ocsp-cache-size`, `--ssl-ocsp-max-age`, `--ssl-crl-mode`, `--ssl-crl`, `--ssl-revocation-fetch` | `tls.*` | `rfc_scoped` | RFC 8446, RFC 5280, RFC 6960, RFC 7301 |
| `proxy_security` | `--proxy-headers`, `--forwarded-allow-ips`, `--root-path`, `--server-header`, `--no-server-header`, `--date-header`, `--no-date-header`, `--header`, `--server-name` | `proxy.*` | `pure_operator` | — |

### `tls`

| Field | Value |
|---|---|
| Flags | `--ssl-certfile`, `--ssl-keyfile`, `--ssl-keyfile-password`, `--ssl-ca-certs`, `--ssl-require-client-cert`, `--ssl-ciphers`, `--ssl-alpn`, `--ssl-ocsp-mode`, `--ssl-ocsp-soft-fail`, `--ssl-ocsp-cache-size`, `--ssl-ocsp-max-age`, `--ssl-crl-mode`, `--ssl-crl`, `--ssl-revocation-fetch` |
| Family | `TLS / security` |
| Config path | `tls.*` |
| Claim class | `rfc_scoped` |
| Default | `defaults file` |
| RFC targets | RFC 8446, RFC 5280, RFC 6960, RFC 7301 |
| Validation rules | `cert/key pairing`, `encrypted key password requires ssl_keyfile`, `CA required for client cert mode`, `OCSP mode enum`, `ocsp max age positive`, `CRL mode enum`, `local CRL path exists and parses`, `revocation fetch toggle` |
| Deployment profiles | `http2_tls`, `http3_quic`, `http3_quic_mtls`, `tls_ocsp_strict` |
| Unit tests | `tests/test_public_api_cli_mtls_surface.py::PublicRunAndCLIClientCertificateSurfaceTests::test_cli_main_forwards_client_certificate_options`, `tests/test_config_matrix.py::ConfigMatrixTests::test_udp_client_auth_is_accepted_with_a_trust_store`, `tests/test_phase5_tls_operator_material_surface.py::Phase5TLSOperatorMaterialSurfaceTests::test_cli_and_env_wiring_accept_ssl_keyfile_password_and_ssl_crl`, `tests/test_phase5_tls_operator_material_surface.py::Phase5TLSOperatorMaterialSurfaceTests::test_encrypted_private_key_material_loads_through_server_tls_context`, `tests/test_phase5_tls_operator_material_surface.py::Phase5TLSOperatorMaterialSurfaceTests::test_local_crl_material_is_loaded_and_revoked_client_cert_is_rejected` |
| Interop scenarios | `http3-server-aioquic-client-mtls`, `tls-server-ocsp-validation-openssl-client` |
| Performance profiles | `tls_handshake` |

### `proxy_security`

| Field | Value |
|---|---|
| Flags | `--proxy-headers`, `--forwarded-allow-ips`, `--root-path`, `--server-header`, `--no-server-header`, `--date-header`, `--no-date-header`, `--header`, `--server-name` |
| Family | `TLS / security` |
| Config path | `proxy.*` |
| Claim class | `pure_operator` |
| Default | `defaults file` |
| RFC targets | — |
| Validation rules | `root_path empty or leading /`, `default headers use name:value syntax`, `server names repeatable / comma-separated allowlist` |
| Deployment profiles | `http1_proxy`, `unix_socket_proxy` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_build_config_from_namespace_maps_nested_submodels` |
| Interop scenarios | — |
| Performance profiles | — |


## Logging / observability

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `logging` | `--log-level`, `--access-log`, `--no-access-log`, `--access-log-file`, `--access-log-format`, `--error-log-file`, `--log-config`, `--structured-log`, `--metrics`, `--metrics-bind`, `--statsd-host`, `--otel-endpoint`, `--use-colors`, `--no-use-colors` | `logging.* / metrics.*` | `pure_operator` | — |

### `logging`

| Field | Value |
|---|---|
| Flags | `--log-level`, `--access-log`, `--no-access-log`, `--access-log-file`, `--access-log-format`, `--error-log-file`, `--log-config`, `--structured-log`, `--metrics`, `--metrics-bind`, `--statsd-host`, `--otel-endpoint`, `--use-colors`, `--no-use-colors` |
| Family | `Logging / observability` |
| Config path | `logging.* / metrics.*` |
| Claim class | `pure_operator` |
| Default | `defaults file` |
| RFC targets | — |
| Validation rules | `path/string/bool parsing`, `optional colorized stream logging toggle` |
| Deployment profiles | `http1_baseline` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_parser_accepts_grouped_phase2_flags` |
| Interop scenarios | — |
| Performance profiles | — |


## Resource / timeouts / concurrency

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `limits` | `--timeout-keep-alive`, `--read-timeout`, `--write-timeout`, `--timeout-graceful-shutdown`, `--limit-concurrency`, `--max-connections`, `--max-tasks`, `--max-streams`, `--max-body-size`, `--max-header-size`, `--http1-max-incomplete-event-size`, `--http1-buffer-size`, `--http1-header-read-timeout`, `--http1-keep-alive`, `--no-http1-keep-alive`, `--http2-max-concurrent-streams`, `--http2-max-headers-size`, `--http2-max-frame-size`, `--http2-adaptive-window`, `--no-http2-adaptive-window`, `--http2-initial-connection-window-size`, `--http2-initial-stream-window-size`, `--http2-keep-alive-interval`, `--http2-keep-alive-timeout`, `--websocket-max-message-size`, `--websocket-max-queue`, `--websocket-ping-interval`, `--websocket-ping-timeout`, `--idle-timeout` | `http.* / websocket.* / scheduler.*` | `hybrid` | RFC 9110, RFC 9112, RFC 9113, RFC 9114, RFC 6455, RFC 8441, RFC 9220 |

### `limits`

| Field | Value |
|---|---|
| Flags | `--timeout-keep-alive`, `--read-timeout`, `--write-timeout`, `--timeout-graceful-shutdown`, `--limit-concurrency`, `--max-connections`, `--max-tasks`, `--max-streams`, `--max-body-size`, `--max-header-size`, `--http1-max-incomplete-event-size`, `--http1-buffer-size`, `--http1-header-read-timeout`, `--http1-keep-alive`, `--no-http1-keep-alive`, `--http2-max-concurrent-streams`, `--http2-max-headers-size`, `--http2-max-frame-size`, `--http2-adaptive-window`, `--no-http2-adaptive-window`, `--http2-initial-connection-window-size`, `--http2-initial-stream-window-size`, `--http2-keep-alive-interval`, `--http2-keep-alive-timeout`, `--websocket-max-message-size`, `--websocket-max-queue`, `--websocket-ping-interval`, `--websocket-ping-timeout`, `--idle-timeout` |
| Family | `Resource / timeouts / concurrency` |
| Config path | `http.* / websocket.* / scheduler.*` |
| Claim class | `hybrid` |
| Default | `defaults file` |
| RFC targets | RFC 9110, RFC 9112, RFC 9113, RFC 9114, RFC 6455, RFC 8441, RFC 9220 |
| Validation rules | `positive numeric values` |
| Deployment profiles | `http1_baseline`, `http2_tls`, `http3_quic`, `websocket_http11` |
| Unit tests | `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_build_config_from_namespace_maps_nested_submodels`, `tests/test_phase3_h1_websocket_operator_surface.py::Phase3H1WebSocketOperatorSurfaceTests::test_build_config_from_namespace_maps_phase3_submodels`, `tests/test_phase4_http2_operator_surface.py::Phase4HTTP2OperatorSurfaceTests::test_build_config_from_namespace_maps_phase4_submodels`, `tests/test_phase4_http2_operator_surface.py::Phase4HTTP2OperatorSurfaceTests::test_http2_server_advertises_configured_local_settings` |
| Interop scenarios | — |
| Performance profiles | `http1_baseline`, `http2_multiplexing`, `http3_clean`, `websocket_echo` |


## Protocol / transport

| Flag group | Flags | Config path | Claim class | RFC targets |
|---|---|---|---|---|
| `protocols` | `--http`, `--protocol`, `--disable-websocket`, `--disable-h2c`, `--websocket-compression`, `--connect-policy`, `--connect-allow`, `--trailer-policy`, `--content-coding-policy`, `--content-codings`, `--alt-svc`, `--alt-svc-auto`, `--no-alt-svc-auto`, `--alt-svc-ma`, `--alt-svc-persist`, `--quic-require-retry`, `--quic-max-datagram-size`, `--quic-idle-timeout`, `--quic-early-data-policy`, `--pipe-mode` | `http.* / websocket.* / quic.* / listeners[].protocols` | `rfc_scoped` | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8 |

### `protocols`

| Field | Value |
|---|---|
| Flags | `--http`, `--protocol`, `--disable-websocket`, `--disable-h2c`, `--websocket-compression`, `--connect-policy`, `--connect-allow`, `--trailer-policy`, `--content-coding-policy`, `--content-codings`, `--alt-svc`, `--alt-svc-auto`, `--no-alt-svc-auto`, `--alt-svc-ma`, `--alt-svc-persist`, `--quic-require-retry`, `--quic-max-datagram-size`, `--quic-idle-timeout`, `--quic-early-data-policy`, `--pipe-mode` |
| Family | `Protocol / transport` |
| Config path | `http.* / websocket.* / quic.* / listeners[].protocols` |
| Claim class | `rfc_scoped` |
| Default | `defaults file` |
| RFC targets | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8 |
| Validation rules | `enum values`, `positive numeric values` |
| Deployment profiles | `http1_baseline`, `http2_cleartext`, `http2_tls`, `http3_quic`, `websocket_http11_permessage_deflate`, `connect_http11`, `trailers_http11`, `content_coding_http11`, `custom_pipe_rawframed`, `websocket_http2_permessage_deflate`, `websocket_http3_permessage_deflate`, `connect_http2`, `connect_http3`, `trailers_http2`, `trailers_http3`, `content_coding_http2`, `content_coding_http3` |
| Unit tests | `tests/test_cli_and_asgi3.py::CLIAndASGI3Tests::test_parser`, `tests/test_phase2_cli_config_surface.py::Phase2CLIConfigSurfaceTests::test_build_config_from_namespace_maps_nested_submodels`, `tests/test_phase3_strict_rfc_surface.py::Phase3StrictRFCSurfaceTests::test_cli_phase3_flags_round_trip_into_config` |
| Interop scenarios | `websocket-http11-server-websockets-client-permessage-deflate`, `http11-connect-relay-curl-client`, `http11-trailer-fields-curl-client`, `http11-content-coding-curl-client`, `http3-server-aioquic-client-post-retry`, `http3-server-aioquic-client-post-zero-rtt`, `websocket-http2-server-h2-client-permessage-deflate`, `websocket-http3-server-aioquic-client-permessage-deflate`, `http2-connect-relay-h2-client`, `http3-connect-relay-aioquic-client`, `http2-trailer-fields-h2-client`, `http3-trailer-fields-aioquic-client`, `http2-content-coding-curl-client`, `http3-content-coding-aioquic-client` |
| Performance profiles | `http1_baseline`, `http2_multiplexing`, `http3_clean`, `websocket_compressed`, `websocket_compression`, `connect_tunnel`, `trailers_under_load`, `content_coding_under_load` |


## Help snapshots

<details>
<summary><strong>`tigrcorn --help` snapshot</strong></summary>

```text
usage: tigrcorn [-h] [--factory] [--app-dir APP_DIR] [--reload]
                [--reload-dir RELOAD_DIR] [--reload-include RELOAD_INCLUDE]
                [--reload-exclude RELOAD_EXCLUDE] [--workers WORKERS]
                [--worker-class WORKER_CLASS]
                [--runtime {auto,asyncio,uvloop}] [--pid PID]
                [--worker-healthcheck-timeout WORKER_HEALTHCHECK_TIMEOUT]
                [--config CONFIG] [--env-file ENV_FILE]
                [--env-prefix ENV_PREFIX] [--lifespan {auto,on,off}]
                [--limit-max-requests LIMIT_MAX_REQUESTS]
                [--max-requests-jitter MAX_REQUESTS_JITTER] [--bind BIND]
                [--host HOST] [--port PORT] [--uds UDS] [--fd FD]
                [--endpoint ENDPOINT] [--insecure-bind INSECURE_BIND]
                [--quic-bind QUIC_BIND]
                [--transport {tcp,udp,unix,pipe,inproc}] [--reuse-port]
                [--reuse-address] [--backlog BACKLOG] [--user USER]
                [--group GROUP] [--umask UMASK]
                [--static-path-route STATIC_PATH_ROUTE]
                [--static-path-mount STATIC_PATH_MOUNT]
                [--static-path-dir-to-file] [--no-static-path-dir-to-file]
                [--static-path-index-file STATIC_PATH_INDEX_FILE]
                [--static-path-expires STATIC_PATH_EXPIRES]
                [--ssl-certfile SSL_CERTFILE] [--ssl-keyfile SSL_KEYFILE]
                [--ssl-keyfile-password SSL_KEYFILE_PASSWORD]
                [--ssl-ca-certs SSL_CA_CERTS] [--ssl-require-client-cert]
                [--ssl-ciphers SSL_CIPHERS] [--ssl-alpn SSL_ALPN]
                [--ssl-ocsp-mode {off,soft-fail,require}]
                [--ssl-ocsp-soft-fail]
                [--ssl-ocsp-cache-size SSL_OCSP_CACHE_SIZE]
                [--ssl-ocsp-max-age SSL_OCSP_MAX_AGE]
                [--ssl-crl-mode {off,soft-fail,require}] [--ssl-crl SSL_CRL]
                [--ssl-revocation-fetch {off,on}] [--proxy-headers]
                [--forwarded-allow-ips FORWARDED_ALLOW_IPS]
                [--root-path ROOT_PATH] [--server-header [SERVER_HEADER]]
                [--no-server-header] [--date-header] [--no-date-header]
                [--header HEADERS] [--server-name SERVER_NAME]
                [--log-level LOG_LEVEL] [--access-log] [--no-access-log]
                [--access-log-file ACCESS_LOG_FILE]
                [--access-log-format ACCESS_LOG_FORMAT]
                [--error-log-file ERROR_LOG_FILE] [--log-config LOG_CONFIG]
                [--structured-log] [--use-colors] [--no-use-colors]
                [--metrics] [--metrics-bind METRICS_BIND]
                [--statsd-host STATSD_HOST] [--otel-endpoint OTEL_ENDPOINT]
                [--timeout-keep-alive TIMEOUT_KEEP_ALIVE]
                [--read-timeout READ_TIMEOUT] [--write-timeout WRITE_TIMEOUT]
                [--timeout-graceful-shutdown TIMEOUT_GRACEFUL_SHUTDOWN]
                [--limit-concurrency LIMIT_CONCURRENCY]
                [--max-connections MAX_CONNECTIONS] [--max-tasks MAX_TASKS]
                [--max-streams MAX_STREAMS] [--max-body-size MAX_BODY_SIZE]
                [--max-header-size MAX_HEADER_SIZE]
                [--http1-max-incomplete-event-size HTTP1_MAX_INCOMPLETE_EVENT_SIZE]
                [--http1-buffer-size HTTP1_BUFFER_SIZE]
                [--http1-header-read-timeout HTTP1_HEADER_READ_TIMEOUT]
                [--http1-keep-alive] [--no-http1-keep-alive]
                [--http2-max-concurrent-streams HTTP2_MAX_CONCURRENT_STREAMS]
                [--http2-max-headers-size HTTP2_MAX_HEADERS_SIZE]
                [--http2-max-frame-size HTTP2_MAX_FRAME_SIZE]
                [--http2-adaptive-window] [--no-http2-adaptive-window]
                [--http2-initial-connection-window-size HTTP2_INITIAL_CONNECTION_WINDOW_SIZE]
                [--http2-initial-stream-window-size HTTP2_INITIAL_STREAM_WINDOW_SIZE]
                [--http2-keep-alive-interval HTTP2_KEEP_ALIVE_INTERVAL]
                [--http2-keep-alive-timeout HTTP2_KEEP_ALIVE_TIMEOUT]
                [--websocket-max-message-size WEBSOCKET_MAX_MESSAGE_SIZE]
                [--websocket-max-queue WEBSOCKET_MAX_QUEUE]
                [--websocket-ping-interval WEBSOCKET_PING_INTERVAL]
                [--websocket-ping-timeout WEBSOCKET_PING_TIMEOUT]
                [--idle-timeout IDLE_TIMEOUT] [--http {1.1,2,3}]
                [--protocol {http1,http2,http3,quic,websocket,rawframed,custom}]
                [--disable-websocket] [--disable-h2c]
                [--websocket-compression {off,permessage-deflate}]
                [--connect-policy {relay,deny,allowlist}]
                [--connect-allow CONNECT_ALLOW]
                [--trailer-policy {pass,drop,strict}]
                [--content-coding-policy {allowlist,identity-only,strict}]
                [--content-codings CONTENT_CODINGS] [--alt-svc ALT_SVC]
                [--alt-svc-auto] [--no-alt-svc-auto] [--alt-svc-ma ALT_SVC_MA]
                [--alt-svc-persist] [--quic-require-retry]
                [--quic-max-datagram-size QUIC_MAX_DATAGRAM_SIZE]
                [--quic-idle-timeout QUIC_IDLE_TIMEOUT]
                [--quic-early-data-policy {allow,deny,require}]
                [--pipe-mode {rawframed,stream}]
                [app]

ASGI3-compatible transport server

positional arguments:
  app                   Application import string in module:attr form

options:
  -h, --help            show this help message and exit

App / process / development:
  --factory             Treat APP as an application factory
  --app-dir APP_DIR     Add a directory to sys.path before loading the app
  --reload              Enable development autoreload
  --reload-dir RELOAD_DIR
                        Directory to watch for reload
  --reload-include RELOAD_INCLUDE
                        Glob to include in reload watch set
  --reload-exclude RELOAD_EXCLUDE
                        Glob to exclude from reload watch set
  --workers WORKERS     Worker process count
  --worker-class WORKER_CLASS
                        Worker implementation class
  --runtime {auto,asyncio,uvloop}
                        Runtime backend for sync entrypoints and worker
                        processes
  --pid PID             PID file path
  --worker-healthcheck-timeout WORKER_HEALTHCHECK_TIMEOUT
                        Worker startup healthcheck timeout in seconds
  --config CONFIG       Config source: file path (.json, .toml, .yaml, .yml,
                        .py), module:<module>, or object:<module>:<name>
  --env-file ENV_FILE   Load additional prefixed config values from a dotenv
                        file
  --env-prefix ENV_PREFIX
                        Environment variable prefix for config loading
  --lifespan {auto,on,off}
  --limit-max-requests LIMIT_MAX_REQUESTS
  --max-requests-jitter MAX_REQUESTS_JITTER

Listener / binding:
  --bind BIND           Bind listener as host:port
  --host HOST           Bind host for TCP/UDP listeners
  --port PORT           Bind port for TCP/UDP listeners
  --uds UDS             Bind Unix domain socket or pipe path
  --fd FD               Use an inherited file descriptor listener
  --endpoint ENDPOINT   Endpoint / raw listener description
  --insecure-bind INSECURE_BIND
                        Additional insecure bind alongside TLS listener(s)
  --quic-bind QUIC_BIND
                        Additional UDP/QUIC bind
  --transport {tcp,udp,unix,pipe,inproc}
  --reuse-port
  --reuse-address
  --backlog BACKLOG
  --user USER           User name or uid to own Unix sockets
  --group GROUP         Group name or gid to own Unix sockets
  --umask UMASK         Umask applied while creating Unix sockets (octal or
                        integer)

Static / delivery:
  --static-path-route STATIC_PATH_ROUTE
                        HTTP route prefix served from the mounted static
                        directory
  --static-path-mount STATIC_PATH_MOUNT
                        Filesystem directory mounted at --static-path-route
  --static-path-dir-to-file
                        directory index resolution for the mounted static path
  --no-static-path-dir-to-file
                        Disable directory index resolution for the mounted
                        static path
  --static-path-index-file STATIC_PATH_INDEX_FILE
                        Index file name served when directory index resolution
                        is enabled
  --static-path-expires STATIC_PATH_EXPIRES
                        Static-response cache TTL in seconds; 0 disables
                        caching headers

TLS / security:
  --ssl-certfile SSL_CERTFILE
                        Certificate for TLS on TCP/Unix or QUIC-TLS on UDP
  --ssl-keyfile SSL_KEYFILE
                        Private key for TLS on TCP/Unix or QUIC-TLS on UDP
  --ssl-keyfile-password SSL_KEYFILE_PASSWORD
                        Password for an encrypted private key PEM used by
                        package-owned TLS/QUIC-TLS listeners
  --ssl-ca-certs SSL_CA_CERTS
                        Trusted CA bundle for client-certificate verification
  --ssl-require-client-cert
                        Require peer client certificates
  --ssl-ciphers SSL_CIPHERS
  --ssl-alpn SSL_ALPN   ALPN protocol(s); repeat or use comma-separated values
  --ssl-ocsp-mode {off,soft-fail,require}
  --ssl-ocsp-soft-fail
  --ssl-ocsp-cache-size SSL_OCSP_CACHE_SIZE
  --ssl-ocsp-max-age SSL_OCSP_MAX_AGE
  --ssl-crl-mode {off,soft-fail,require}
  --ssl-crl SSL_CRL     Local CRL file (PEM or DER) loaded into the package-
                        owned revocation material set
  --ssl-revocation-fetch {off,on}
  --proxy-headers
  --forwarded-allow-ips FORWARDED_ALLOW_IPS
                        Trusted forwarded-header peers; repeat or use comma-
                        separated values
  --root-path ROOT_PATH
                        ASGI root_path mount prefix
  --server-header [SERVER_HEADER]
                        Enable or override the Server header value
  --no-server-header    Disable the Server header
  --date-header         Date header injection
  --no-date-header      Disable date header injection
  --header HEADERS      Default response header in name:value form; repeat to
                        add multiple headers
  --server-name SERVER_NAME
                        Allowed Host/:authority value; repeat or use comma-
                        separated values

Logging / observability:
  --log-level LOG_LEVEL
  --access-log          Access logging
  --no-access-log       Disable access logging
  --access-log-file ACCESS_LOG_FILE
  --access-log-format ACCESS_LOG_FORMAT
  --error-log-file ERROR_LOG_FILE
  --log-config LOG_CONFIG
  --structured-log
  --use-colors          Colorized logging
  --no-use-colors       Disable colorized logging
  --metrics
  --metrics-bind METRICS_BIND
  --statsd-host STATSD_HOST
  --otel-endpoint OTEL_ENDPOINT

Resource / timeouts / concurrency:
  --timeout-keep-alive TIMEOUT_KEEP_ALIVE
  --read-timeout READ_TIMEOUT
  --write-timeout WRITE_TIMEOUT
  --timeout-graceful-shutdown TIMEOUT_GRACEFUL_SHUTDOWN
  --limit-concurrency LIMIT_CONCURRENCY
  --max-connections MAX_CONNECTIONS
  --max-tasks MAX_TASKS
  --max-streams MAX_STREAMS
  --max-body-size MAX_BODY_SIZE
  --max-header-size MAX_HEADER_SIZE
  --http1-max-incomplete-event-size HTTP1_MAX_INCOMPLETE_EVENT_SIZE
                        Cap buffered incomplete HTTP/1.1 request-head bytes
                        before the parser rejects the request
  --http1-buffer-size HTTP1_BUFFER_SIZE
                        Read-buffer size used for HTTP/1.1 request-head/body
                        incremental reads
  --http1-header-read-timeout HTTP1_HEADER_READ_TIMEOUT
                        HTTP/1.1 request-head read timeout in seconds; when
                        set it tightens the generic read/keep-alive timeout
  --http1-keep-alive    HTTP/1.1 connection persistence
  --no-http1-keep-alive
                        Disable http/1.1 connection persistence
  --http2-max-concurrent-streams HTTP2_MAX_CONCURRENT_STREAMS
                        Advertised HTTP/2 MAX_CONCURRENT_STREAMS value for
                        inbound peer-created streams
  --http2-max-headers-size HTTP2_MAX_HEADERS_SIZE
                        HTTP/2-specific request-header and decoded header-list
                        size cap
  --http2-max-frame-size HTTP2_MAX_FRAME_SIZE
                        Advertised HTTP/2 MAX_FRAME_SIZE for inbound peer
                        frames
  --http2-adaptive-window
                        HTTP/2 adaptive receive-window growth
  --no-http2-adaptive-window
                        Disable http/2 adaptive receive-window growth
  --http2-initial-connection-window-size HTTP2_INITIAL_CONNECTION_WINDOW_SIZE
                        HTTP/2 connection-level receive window target; values
                        below 65535 are clamped to the protocol default
  --http2-initial-stream-window-size HTTP2_INITIAL_STREAM_WINDOW_SIZE
                        Advertised HTTP/2 INITIAL_WINDOW_SIZE for peer-created
                        streams
  --http2-keep-alive-interval HTTP2_KEEP_ALIVE_INTERVAL
                        Idle interval before the server sends an HTTP/2
                        connection-level PING
  --http2-keep-alive-timeout HTTP2_KEEP_ALIVE_TIMEOUT
                        HTTP/2 keep-alive PING acknowledgement timeout in
                        seconds
  --websocket-max-message-size WEBSOCKET_MAX_MESSAGE_SIZE
  --websocket-max-queue WEBSOCKET_MAX_QUEUE
                        Maximum queued inbound WebSocket messages before
                        transport backpressure is applied
  --websocket-ping-interval WEBSOCKET_PING_INTERVAL
  --websocket-ping-timeout WEBSOCKET_PING_TIMEOUT
  --idle-timeout IDLE_TIMEOUT

Protocol / transport:
  --http {1.1,2,3}      Enable an HTTP version
  --protocol {http1,http2,http3,quic,websocket,rawframed,custom}
                        Enable a listener protocol
  --disable-websocket
  --disable-h2c
  --websocket-compression {off,permessage-deflate}
  --connect-policy {relay,deny,allowlist}
  --connect-allow CONNECT_ALLOW
                        Repeat or use comma-separated host:port, host, or CIDR
                        entries
  --trailer-policy {pass,drop,strict}
  --content-coding-policy {allowlist,identity-only,strict}
  --content-codings CONTENT_CODINGS
                        Repeat or use comma-separated values
  --alt-svc ALT_SVC     Advertise Alt-Svc values; repeat or use comma-
                        separated values
  --alt-svc-auto        automatic Alt-Svc advertisement for HTTP/3-capable UDP
                        listeners
  --no-alt-svc-auto     Disable automatic alt-svc advertisement for
                        http/3-capable udp listeners
  --alt-svc-ma ALT_SVC_MA
                        Alt-Svc max-age for automatic advertisement
  --alt-svc-persist     Set persist=1 on automatic Alt-Svc advertisements
  --quic-require-retry  Require a QUIC Retry before completing the initial
                        handshake
  --quic-max-datagram-size QUIC_MAX_DATAGRAM_SIZE
  --quic-idle-timeout QUIC_IDLE_TIMEOUT
  --quic-early-data-policy {allow,deny,require}
  --pipe-mode {rawframed,stream}
```

</details>

<details>
<summary><strong>`tigrcorn-interop --help` snapshot</strong></summary>

```text
usage: tigrcorn-interop [-h] --matrix MATRIX --output OUTPUT
                        [--source-root SOURCE_ROOT] [--only SCENARIO_IDS]
                        [--strict]

Run the tigrcorn external interoperability matrix and write evidence bundles

options:
  -h, --help            show this help message and exit
  --matrix MATRIX       Path to the external interop matrix JSON file
  --output OUTPUT       Root directory for result bundles
  --source-root SOURCE_ROOT
                        Repository root used for manifest hashing and commit
                        detection
  --only SCENARIO_IDS   Run only the named scenario id (may be given multiple
                        times)
  --strict              Stop after the first failed scenario
```

</details>

## Notes on hidden or non-public flags

- `--quic-secret` exists in the parser but is intentionally hidden from the public help and excluded from the public certified CLI surface.
- When public CLI behavior changes, maintainers must update code, tests, `cli_flag_surface.json`, the human CLI docs, and current-state/promotion docs together.
