# Generated Default Tables

This page is generated from the runtime default audit and reviewed flag-contract registry.

| Flag | Config path | Parser default | Effective default | Review |
|---|---|---|---|---|
| `--access-log` | `logging.access_log` | `None` | `True` | `reviewed_phase2` |
| `--access-log-file` | `logging.access_log_file` | `None` | `None` | `reviewed_phase2` |
| `--access-log-format` | `logging.access_log_format` | `None` | `None` | `reviewed_phase2` |
| `--alt-svc` | `http.alt_svc_headers` | `None` | `[]` | `reviewed_phase2` |
| `--alt-svc-auto` | `http.alt_svc_auto` | `None` | `False` | `reviewed_phase2` |
| `--alt-svc-ma` | `http.alt_svc_max_age` | `None` | `86400` | `reviewed_phase2` |
| `--alt-svc-persist` | `http.alt_svc_persist` | `None` | `False` | `reviewed_phase2` |
| `--app-dir` | `app.app_dir` | `None` | `None` | `reviewed_phase2` |
| `--backlog` | `listeners[].backlog` | `None` | `2048` | `reviewed_phase2` |
| `--bind` | `listeners[].bind` | `None` | `None` | `reviewed_phase2` |
| `--config` | `app.config_file` | `None` | `None` | `reviewed_phase2` |
| `--connect-allow` | `http.connect_allow` | `None` | `[]` | `reviewed_phase2` |
| `--connect-policy` | `http.connect_policy` | `None` | `deny` | `reviewed_phase2` |
| `--content-coding-policy` | `http.content_coding_policy` | `None` | `allowlist` | `reviewed_phase2` |
| `--content-codings` | `http.content_codings` | `None` | `None` | `reviewed_phase2` |
| `--date-header` | `proxy.include_date_header` | `None` | `True` | `reviewed_phase2` |
| `--header` | `proxy.default_headers[]` | `None` | `None` | `reviewed_phase2` |
| `--disable-h2c` | `http.enable_h2c` | `None` | `False` | `reviewed_phase2` |
| `--disable-websocket` | `websocket.enabled` | `None` | `False` | `reviewed_phase2` |
| `--endpoint` | `listeners[].endpoint` | `None` | `None` | `reviewed_phase2` |
| `--env-file` | `app.env_file` | `None` | `None` | `reviewed_phase2` |
| `--env-prefix` | `app.env_prefix` | `None` | `TIGRCORN` | `reviewed_phase2` |
| `--error-log-file` | `logging.error_log_file` | `None` | `None` | `reviewed_phase2` |
| `--factory` | `app.factory` | `None` | `False` | `reviewed_phase2` |
| `--fd` | `listeners[].fd` | `None` | `None` | `reviewed_phase2` |
| `--forwarded-allow-ips` | `proxy.forwarded_allow_ips` | `None` | `[]` | `reviewed_phase2` |
| `--host` | `listeners[].host` | `None` | `127.0.0.1` | `reviewed_phase2` |
| `--http` | `http.http_versions` | `None` | `None` | `reviewed_phase2` |
| `--http1-buffer-size` | `http.http1_buffer_size` | `None` | `65536` | `reviewed_phase2` |
| `--http1-header-read-timeout` | `http.http1_header_read_timeout` | `None` | `None` | `reviewed_phase2` |
| `--http1-keep-alive` | `http.http1_keep_alive` | `None` | `True` | `reviewed_phase2` |
| `--http1-max-incomplete-event-size` | `http.http1_max_incomplete_event_size` | `None` | `65536` | `reviewed_phase2` |
| `--http2-adaptive-window` | `http.http2_adaptive_window` | `None` | `False` | `reviewed_phase2` |
| `--http2-initial-connection-window-size` | `http.http2_initial_connection_window_size` | `None` | `65535` | `reviewed_phase2` |
| `--http2-initial-stream-window-size` | `http.http2_initial_stream_window_size` | `None` | `65535` | `reviewed_phase2` |
| `--http2-keep-alive-interval` | `http.http2_keep_alive_interval` | `None` | `None` | `reviewed_phase2` |
| `--http2-keep-alive-timeout` | `http.http2_keep_alive_timeout` | `None` | `None` | `reviewed_phase2` |
| `--http2-max-concurrent-streams` | `http.http2_max_concurrent_streams` | `None` | `128` | `reviewed_phase2` |
| `--http2-max-frame-size` | `http.http2_max_frame_size` | `None` | `16384` | `reviewed_phase2` |
| `--http2-max-headers-size` | `http.http2_max_headers_size` | `None` | `65536` | `reviewed_phase2` |
| `--idle-timeout` | `http.idle_timeout` | `None` | `30.0` | `reviewed_phase2` |
| `--insecure-bind` | `listeners[].insecure_bind` | `None` | `None` | `reviewed_phase2` |
| `--lifespan` | `app.lifespan` | `None` | `auto` | `reviewed_phase2` |
| `--limit-concurrency` | `scheduler.limit_concurrency` | `None` | `None` | `reviewed_phase2` |
| `--limit-max-requests` | `process.limit_max_requests` | `None` | `None` | `reviewed_phase2` |
| `--log-config` | `logging.log_config` | `None` | `None` | `reviewed_phase2` |
| `--log-level` | `logging.level` | `None` | `info` | `reviewed_phase2` |
| `--max-body-size` | `http.max_body_size` | `None` | `16777216` | `reviewed_phase2` |
| `--max-connections` | `scheduler.max_connections` | `None` | `None` | `reviewed_phase2` |
| `--max-header-size` | `http.max_header_size` | `None` | `65536` | `reviewed_phase2` |
| `--max-requests-jitter` | `process.max_requests_jitter` | `None` | `0` | `reviewed_phase2` |
| `--max-streams` | `scheduler.max_streams` | `None` | `None` | `reviewed_phase2` |
| `--max-tasks` | `scheduler.max_tasks` | `None` | `None` | `reviewed_phase2` |
| `--metrics` | `metrics.enabled` | `None` | `False` | `reviewed_phase2` |
| `--metrics-bind` | `metrics.bind` | `None` | `None` | `reviewed_phase2` |
| `--no-access-log` | `logging.access_log` | `None` | `True` | `reviewed_phase2` |
| `--no-alt-svc-auto` | `http.alt_svc_auto` | `None` | `False` | `reviewed_phase2` |
| `--no-date-header` | `proxy.include_date_header` | `None` | `True` | `reviewed_phase2` |
| `--no-http1-keep-alive` | `http.http1_keep_alive` | `None` | `True` | `reviewed_phase2` |
| `--no-http2-adaptive-window` | `http.http2_adaptive_window` | `None` | `False` | `reviewed_phase2` |
| `--no-server-header` | `proxy.include_server_header` | `False` | `False` | `reviewed_phase2` |
| `--no-static-path-dir-to-file` | `static.dir_to_file` | `None` | `True` | `reviewed_phase2` |
| `--no-use-colors` | `logging.use_colors` | `None` | `None` | `reviewed_phase2` |
| `--otel-endpoint` | `metrics.otel_endpoint` | `None` | `None` | `reviewed_phase2` |
| `--pid` | `process.pid_file` | `None` | `None` | `reviewed_phase2` |
| `--pipe-mode` | `listeners[].pipe_mode` | `None` | `rawframed` | `reviewed_phase2` |
| `--port` | `listeners[].port` | `None` | `8000` | `reviewed_phase2` |
| `--protocol` | `listeners[].protocols` | `None` | `None` | `reviewed_phase2` |
| `--proxy-headers` | `proxy.proxy_headers` | `None` | `False` | `reviewed_phase2` |
| `--quic-bind` | `listeners[].quic_bind` | `None` | `None` | `reviewed_phase2` |
| `--quic-early-data-policy` | `quic.early_data_policy` | `None` | `deny` | `reviewed_phase2` |
| `--quic-idle-timeout` | `quic.idle_timeout` | `None` | `30.0` | `reviewed_phase2` |
| `--quic-max-datagram-size` | `quic.max_datagram_size` | `None` | `1200` | `reviewed_phase2` |
| `--quic-require-retry` | `quic.require_retry` | `None` | `False` | `reviewed_phase2` |
| `--read-timeout` | `http.read_timeout` | `None` | `30.0` | `reviewed_phase2` |
| `--reload` | `app.reload` | `None` | `False` | `reviewed_phase2` |
| `--reload-dir` | `app.reload_dirs` | `None` | `[]` | `reviewed_phase2` |
| `--reload-exclude` | `app.reload_exclude` | `None` | `[]` | `reviewed_phase2` |
| `--reload-include` | `app.reload_include` | `None` | `[]` | `reviewed_phase2` |
| `--reuse-address` | `listeners[].reuse_address` | `None` | `True` | `reviewed_phase2` |
| `--reuse-port` | `listeners[].reuse_port` | `None` | `False` | `reviewed_phase2` |
| `--root-path` | `proxy.root_path` | `None` | `` | `reviewed_phase2` |
| `--runtime` | `process.runtime` | `None` | `auto` | `reviewed_phase2` |
| `--server-header` | `proxy.server_header` | `None` | `` | `reviewed_phase2` |
| `--server-name` | `proxy.server_names[]` | `None` | `None` | `reviewed_phase2` |
| `--ssl-alpn` | `tls.alpn_protocols` | `None` | `None` | `reviewed_phase2` |
| `--ssl-ca-certs` | `tls.ca_certs` | `None` | `None` | `reviewed_phase2` |
| `--ssl-certfile` | `tls.certfile` | `None` | `None` | `reviewed_phase2` |
| `--ssl-ciphers` | `tls.ciphers` | `None` | `None` | `reviewed_phase2` |
| `--ssl-crl` | `tls.crl` | `None` | `None` | `reviewed_phase2` |
| `--ssl-crl-mode` | `tls.crl_mode` | `None` | `off` | `reviewed_phase2` |
| `--ssl-keyfile` | `tls.keyfile` | `None` | `None` | `reviewed_phase2` |
| `--ssl-keyfile-password` | `tls.keyfile_password` | `None` | `None` | `reviewed_phase2` |
| `--ssl-ocsp-cache-size` | `tls.ocsp_cache_size` | `None` | `128` | `reviewed_phase2` |
| `--ssl-ocsp-max-age` | `tls.ocsp_max_age` | `None` | `43200.0` | `reviewed_phase2` |
| `--ssl-ocsp-mode` | `tls.ocsp_mode` | `None` | `off` | `reviewed_phase2` |
| `--ssl-ocsp-soft-fail` | `tls.ocsp_soft_fail` | `None` | `False` | `reviewed_phase2` |
| `--ssl-require-client-cert` | `tls.require_client_cert` | `None` | `False` | `reviewed_phase2` |
| `--ssl-revocation-fetch` | `tls.revocation_fetch` | `None` | `True` | `reviewed_phase2` |
| `--static-path-dir-to-file` | `static.dir_to_file` | `None` | `True` | `reviewed_phase2` |
| `--static-path-expires` | `static.expires` | `None` | `None` | `reviewed_phase2` |
| `--static-path-index-file` | `static.index_file` | `None` | `index.html` | `reviewed_phase2` |
| `--static-path-mount` | `static.mount` | `None` | `None` | `reviewed_phase2` |
| `--static-path-route` | `static.route` | `None` | `None` | `reviewed_phase2` |
| `--statsd-host` | `metrics.statsd_host` | `None` | `None` | `reviewed_phase2` |
| `--structured-log` | `logging.structured` | `None` | `False` | `reviewed_phase2` |
| `--timeout-graceful-shutdown` | `http.shutdown_timeout` | `None` | `30.0` | `reviewed_phase2` |
| `--timeout-keep-alive` | `http.keep_alive_timeout` | `None` | `5.0` | `reviewed_phase2` |
| `--trailer-policy` | `http.trailer_policy` | `None` | `pass` | `reviewed_phase2` |
| `--transport` | `listeners[].kind` | `None` | `tcp` | `reviewed_phase2` |
| `--uds` | `listeners[].path` | `None` | `None` | `reviewed_phase2` |
| `--group` | `listeners[].group` | `None` | `None` | `reviewed_phase2` |
| `--umask` | `listeners[].umask` | `None` | `None` | `reviewed_phase2` |
| `--user` | `listeners[].user` | `None` | `None` | `reviewed_phase2` |
| `--use-colors` | `logging.use_colors` | `None` | `None` | `reviewed_phase2` |
| `--websocket-compression` | `websocket.compression` | `None` | `off` | `reviewed_phase2` |
| `--websocket-max-message-size` | `websocket.max_message_size` | `None` | `16777216` | `reviewed_phase2` |
| `--websocket-max-queue` | `websocket.max_queue` | `None` | `32` | `reviewed_phase2` |
| `--websocket-ping-interval` | `websocket.ping_interval` | `None` | `None` | `reviewed_phase2` |
| `--websocket-ping-timeout` | `websocket.ping_timeout` | `None` | `None` | `reviewed_phase2` |
| `--worker-class` | `process.worker_class` | `None` | `local` | `reviewed_phase2` |
| `--worker-healthcheck-timeout` | `process.worker_healthcheck_timeout` | `None` | `30.0` | `reviewed_phase2` |
| `--workers` | `process.workers` | `None` | `1` | `reviewed_phase2` |
| `--write-timeout` | `http.write_timeout` | `None` | `30.0` | `reviewed_phase2` |

## Profile audits

| Profile | JSON | Markdown | Overlay keys |
|---|---|---|---|
| `default` | `PROFILE_DEFAULTS/default.json` | `PROFILE_DEFAULTS/default.md` | `0` |
| `strict-h1-origin` | `PROFILE_DEFAULTS/strict-h1-origin.json` | `PROFILE_DEFAULTS/strict-h1-origin.md` | `2` |
| `strict-h2-origin` | `PROFILE_DEFAULTS/strict-h2-origin.json` | `PROFILE_DEFAULTS/strict-h2-origin.md` | `89` |
| `strict-h3-edge` | `PROFILE_DEFAULTS/strict-h3-edge.json` | `PROFILE_DEFAULTS/strict-h3-edge.md` | `134` |
| `strict-mtls-origin` | `PROFILE_DEFAULTS/strict-mtls-origin.json` | `PROFILE_DEFAULTS/strict-mtls-origin.md` | `95` |
| `static-origin` | `PROFILE_DEFAULTS/static-origin.json` | `PROFILE_DEFAULTS/static-origin.md` | `12` |
