from __future__ import annotations

from pathlib import Path

from tigrcorn.config.model import ServerConfig
from tigrcorn.constants import SUPPORTED_RUNTIMES, SUPPORTED_WORKER_CLASS_ALIASES
from tigrcorn.protocols.connect import validate_connect_allow_entry
from tigrcorn.observability.logging import validate_logging_contract
from tigrcorn.observability.metrics import parse_statsd_host
from tigrcorn.observability.tracing import validate_otel_endpoint
from tigrcorn.errors import ConfigError

_ALLOWED_PROTOCOLS = {"http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"}
_ALLOWED_WORKER_CLASSES = {"local", "process", *SUPPORTED_WORKER_CLASS_ALIASES}
_ALLOWED_RUNTIMES = set(SUPPORTED_RUNTIMES)


def _require_positive(name: str, value: int | float | None) -> None:
    if value is not None and value <= 0:
        raise ConfigError(f"{name} must be positive")


def validate_config(config: ServerConfig) -> None:
    if config.app.lifespan not in {"auto", "on", "off"}:
        raise ConfigError(f"invalid lifespan mode: {config.app.lifespan!r}")
    if config.process.workers <= 0:
        raise ConfigError("workers must be positive")
    if config.process.worker_class not in _ALLOWED_WORKER_CLASSES:
        raise ConfigError(f"unsupported worker_class: {config.process.worker_class!r}")
    if config.process.runtime not in _ALLOWED_RUNTIMES:
        raise ConfigError(f"unsupported runtime: {config.process.runtime!r}")

    if config.app.reload and config.process.workers != 1:
        raise ConfigError('reload requires workers == 1')
    if config.app.reload and config.process.worker_class not in {'local', 'process'}:
        raise ConfigError('reload only supports local/process worker classes')
    if config.metrics.bind and ':' not in config.metrics.bind:
        raise ConfigError('metrics.bind must be host:port')
    if config.metrics.statsd_host is not None:
        try:
            parse_statsd_host(config.metrics.statsd_host)
        except Exception as exc:
            raise ConfigError('statsd_host must be host:port') from exc
    if config.metrics.otel_endpoint is not None:
        try:
            validate_otel_endpoint(config.metrics.otel_endpoint)
        except Exception as exc:
            raise ConfigError('otel_endpoint must be an http:// or https:// URL') from exc
    try:
        validate_logging_contract(config.logging)
    except Exception as exc:
        raise ConfigError(str(exc)) from exc
    if config.proxy.forwarded_allow_ips:
        for entry in config.proxy.forwarded_allow_ips:
            if not entry:
                raise ConfigError('forwarded_allow_ips entries cannot be empty')

    for field_name, value in {
        "max_body_size": config.http.max_body_size,
        "max_header_size": config.http.max_header_size,
        "http.http1_max_incomplete_event_size": config.http.http1_max_incomplete_event_size,
        "http.http1_buffer_size": config.http.http1_buffer_size,
        "http.http1_header_read_timeout": config.http.http1_header_read_timeout,
        "http.http2_max_concurrent_streams": config.http.http2_max_concurrent_streams,
        "http.http2_max_headers_size": config.http.http2_max_headers_size,
        "http.http2_initial_connection_window_size": config.http.http2_initial_connection_window_size,
        "http.http2_initial_stream_window_size": config.http.http2_initial_stream_window_size,
        "http.http2_keep_alive_interval": config.http.http2_keep_alive_interval,
        "http.http2_keep_alive_timeout": config.http.http2_keep_alive_timeout,
        "keep_alive_timeout": config.http.keep_alive_timeout,
        "read_timeout": config.http.read_timeout,
        "write_timeout": config.http.write_timeout,
        "shutdown_timeout": config.http.shutdown_timeout,
        "idle_timeout": config.http.idle_timeout,
        "websocket.max_message_size": config.websocket.max_message_size,
        "websocket.max_queue": config.websocket.max_queue,
        "websocket.ping_interval": config.websocket.ping_interval,
        "websocket.ping_timeout": config.websocket.ping_timeout,
        "quic.max_datagram_size": config.quic.max_datagram_size,
        "quic.idle_timeout": config.quic.idle_timeout,
        "tls.ocsp_cache_size": config.tls.ocsp_cache_size,
        "scheduler.limit_concurrency": config.scheduler.limit_concurrency,
        "scheduler.max_connections": config.scheduler.max_connections,
        "scheduler.max_tasks": config.scheduler.max_tasks,
        "scheduler.max_streams": config.scheduler.max_streams,
        "process.worker_healthcheck_timeout": config.process.worker_healthcheck_timeout,
    }.items():
        _require_positive(field_name, value)

    if config.http.alt_svc_max_age < 0:
        raise ConfigError('http.alt_svc_max_age must be non-negative')
    if not (16_384 <= config.http.http2_max_frame_size <= 16_777_215):
        raise ConfigError('http.http2_max_frame_size must be between 16384 and 16777215')
    if config.http.http2_initial_connection_window_size < 65_535 or config.http.http2_initial_connection_window_size > 0x7FFFFFFF:
        raise ConfigError('http.http2_initial_connection_window_size must be between 65535 and 2147483647')
    if config.http.http2_initial_stream_window_size <= 0 or config.http.http2_initial_stream_window_size > 0x7FFFFFFF:
        raise ConfigError('http.http2_initial_stream_window_size must be between 1 and 2147483647')
    for value in config.http.alt_svc_headers:
        if not str(value).strip():
            raise ConfigError('http.alt_svc_headers entries cannot be empty')

    if config.http.connect_policy not in {"relay", "deny", "allowlist"}:
        raise ConfigError(f"unsupported connect_policy: {config.http.connect_policy!r}")
    if config.http.trailer_policy not in {"pass", "drop", "strict"}:
        raise ConfigError(f"unsupported trailer_policy: {config.http.trailer_policy!r}")
    if config.http.content_coding_policy not in {"allowlist", "identity-only", "strict"}:
        raise ConfigError(f"unsupported content_coding_policy: {config.http.content_coding_policy!r}")
    if config.websocket.compression not in {"off", "permessage-deflate"}:
        raise ConfigError(f"unsupported websocket compression mode: {config.websocket.compression!r}")
    if config.quic.early_data_policy not in {"allow", "deny", "require"}:
        raise ConfigError(f"unsupported quic early data policy: {config.quic.early_data_policy!r}")
    if config.tls.ocsp_mode not in {"off", "soft-fail", "require"}:
        raise ConfigError(f"unsupported ocsp_mode: {config.tls.ocsp_mode!r}")
    if config.tls.crl_mode not in {"off", "soft-fail", "require"}:
        raise ConfigError(f"unsupported crl_mode: {config.tls.crl_mode!r}")
    if config.tls.keyfile_password is not None and not config.tls.keyfile:
        raise ConfigError('tls.keyfile_password requires tls.keyfile')
    if config.tls.crl is not None and not Path(config.tls.crl).exists():
        raise ConfigError(f'tls.crl does not exist: {config.tls.crl}')
    _require_positive('tls.ocsp_max_age', config.tls.ocsp_max_age)
    if config.tls.ciphers is not None and not config.tls.resolved_cipher_suites:
        raise ConfigError('ssl_ciphers must resolve to at least one supported TLS 1.3 cipher suite')
    for entry in config.http.connect_allow:
        try:
            validate_connect_allow_entry(entry)
        except Exception as exc:
            raise ConfigError(f'invalid connect_allow entry: {entry!r}') from exc
    if config.proxy.root_path and not config.proxy.root_path.startswith('/'):
        raise ConfigError("root_path must be empty or start with '/'")
    if config.static.route and not config.static.route.startswith('/'):
        raise ConfigError("static.route must be empty or start with '/'")
    if config.static.route and not config.static.mount:
        raise ConfigError('static.mount is required when static.route is configured')
    if config.static.expires is not None and config.static.expires < 0:
        raise ConfigError('static.expires must be non-negative')

    for name, value in config.default_response_headers:
        if not bytes(name).strip():
            raise ConfigError('default_headers entries require a non-empty name')
        if b':' in bytes(name):
            raise ConfigError('default_headers names must not contain a colon')
    for server_name in config.allowed_server_names:
        if not server_name:
            raise ConfigError('server_names entries cannot be empty')

    for listener in config.listeners:
        if listener.kind in {"tcp", "udp"}:
            if listener.fd is None and not listener.endpoint:
                if not listener.host:
                    raise ConfigError(f"{listener.kind} listener host cannot be empty")
                if listener.port < 0 or listener.port > 65535:
                    raise ConfigError(f"invalid {listener.kind.upper()} port: {listener.port}")
        elif listener.kind in {"unix", "pipe"}:
            if not listener.path and listener.fd is None and not listener.endpoint:
                raise ConfigError(f"{listener.kind} listener requires a path, fd, or endpoint")
        elif listener.kind != "inproc":
            raise ConfigError(f"unsupported listener kind: {listener.kind!r}")

        if listener.fd is not None and listener.fd < 0:
            raise ConfigError('listener fd must be non-negative')
        if listener.kind != "unix" and any(value is not None for value in (listener.user, listener.group, listener.umask)):
            raise ConfigError('user/group/umask are only supported on unix listeners')
        if listener.umask is not None and not (0 <= listener.umask <= 0o777):
            raise ConfigError('listener umask must be between 0 and 0o777')
        if listener.ssl_certfile and not listener.ssl_keyfile:
            raise ConfigError("ssl_keyfile is required when ssl_certfile is set")
        if listener.ssl_keyfile and not listener.ssl_certfile:
            raise ConfigError("ssl_certfile is required when ssl_keyfile is set")
        if getattr(listener, 'ssl_keyfile_password', None) is not None and not listener.ssl_keyfile:
            raise ConfigError('ssl_keyfile_password requires ssl_keyfile')
        if getattr(listener, 'ssl_crl', None) is not None and not Path(str(listener.ssl_crl)).exists():
            raise ConfigError(f'listener ssl_crl does not exist: {listener.ssl_crl}')
        if getattr(listener, 'ssl_crl', None) is not None and not listener.ssl_enabled:
            raise ConfigError('ssl_crl requires ssl_certfile and ssl_keyfile on listeners')
        if getattr(listener, 'ssl_ciphers', None) is not None and not getattr(listener, 'resolved_cipher_suites', ()):
            raise ConfigError('listener ssl_ciphers must resolve to at least one supported TLS 1.3 cipher suite')
        bad_versions = [v for v in listener.http_versions if v not in {"1.1", "2", "3"}]
        if bad_versions:
            raise ConfigError(f"unsupported http_versions: {bad_versions!r}")
        bad_protocols = [v for v in listener.enabled_protocols if v not in _ALLOWED_PROTOCOLS]
        if bad_protocols:
            raise ConfigError(f"unsupported listener protocols: {bad_protocols!r}")
        if getattr(listener, 'ocsp_mode', 'off') not in {"off", "soft-fail", "require"}:
            raise ConfigError(f'unsupported listener ocsp_mode: {listener.ocsp_mode!r}')
        if getattr(listener, 'crl_mode', 'off') not in {"off", "soft-fail", "require"}:
            raise ConfigError(f'unsupported listener crl_mode: {listener.crl_mode!r}')
        _require_positive('listener.ocsp_cache_size', getattr(listener, 'ocsp_cache_size', None))
        _require_positive('listener.ocsp_max_age', getattr(listener, 'ocsp_max_age', None))
        if listener.kind in {"tcp", "unix"}:
            if listener.ssl_ca_certs and not listener.ssl_enabled:
                raise ConfigError(f"ssl_ca_certs requires ssl_certfile and ssl_keyfile on {listener.kind} listeners")
            if listener.ssl_require_client_cert:
                if not listener.ssl_enabled:
                    raise ConfigError(f"ssl_require_client_cert requires ssl_certfile and ssl_keyfile on {listener.kind} listeners")
                if not listener.ssl_ca_certs:
                    raise ConfigError(f"ssl_ca_certs is required when ssl_require_client_cert is enabled for {listener.kind} listeners")
        if listener.kind == "udp":
            if listener.max_datagram_size <= 0:
                raise ConfigError("max_datagram_size must be positive for udp listeners")
            if "http3" in listener.enabled_protocols and "quic" not in listener.enabled_protocols:
                raise ConfigError("http3 requires quic on udp listeners")
            if listener.ssl_ca_certs and not listener.ssl_enabled:
                raise ConfigError("ssl_ca_certs requires ssl_certfile and ssl_keyfile on udp listeners")
            if listener.ssl_require_client_cert:
                if not listener.ssl_enabled:
                    raise ConfigError("ssl_require_client_cert requires ssl_certfile and ssl_keyfile on udp listeners")
                if not listener.ssl_ca_certs:
                    raise ConfigError("ssl_ca_certs is required when ssl_require_client_cert is enabled for udp listeners")
        if listener.kind == "pipe" and listener.pipe_mode not in {"rawframed", "stream"}:
            raise ConfigError(f"unsupported pipe mode: {listener.pipe_mode!r}")
