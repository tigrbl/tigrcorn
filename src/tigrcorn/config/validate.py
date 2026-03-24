from __future__ import annotations

from tigrcorn.config.model import ServerConfig
from tigrcorn.protocols.connect import validate_connect_allow_entry
from tigrcorn.observability.logging import validate_logging_contract
from tigrcorn.observability.metrics import parse_statsd_host
from tigrcorn.observability.tracing import validate_otel_endpoint
from tigrcorn.errors import ConfigError

_ALLOWED_PROTOCOLS = {"http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"}
_ALLOWED_WORKER_CLASSES = {"local", "process", "asyncio", "uvloop", "trio"}


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
        "keep_alive_timeout": config.http.keep_alive_timeout,
        "read_timeout": config.http.read_timeout,
        "write_timeout": config.http.write_timeout,
        "shutdown_timeout": config.http.shutdown_timeout,
        "idle_timeout": config.http.idle_timeout,
        "websocket.max_message_size": config.websocket.max_message_size,
        "websocket.ping_interval": config.websocket.ping_interval,
        "websocket.ping_timeout": config.websocket.ping_timeout,
        "quic.max_datagram_size": config.quic.max_datagram_size,
        "quic.idle_timeout": config.quic.idle_timeout,
        "tls.ocsp_cache_size": config.tls.ocsp_cache_size,
        "scheduler.limit_concurrency": config.scheduler.limit_concurrency,
        "scheduler.max_connections": config.scheduler.max_connections,
        "scheduler.max_tasks": config.scheduler.max_tasks,
        "scheduler.max_streams": config.scheduler.max_streams,
    }.items():
        _require_positive(field_name, value)

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
        if listener.ssl_certfile and not listener.ssl_keyfile:
            raise ConfigError("ssl_keyfile is required when ssl_certfile is set")
        if listener.ssl_keyfile and not listener.ssl_certfile:
            raise ConfigError("ssl_certfile is required when ssl_keyfile is set")
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
