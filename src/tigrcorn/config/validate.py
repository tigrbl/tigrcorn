from __future__ import annotations

from tigrcorn.config.model import ServerConfig
from tigrcorn.errors import ConfigError

_ALLOWED_PROTOCOLS = {"http1", "http2", "http3", "quic", "websocket", "rawframed", "custom"}


def validate_config(config: ServerConfig) -> None:
    if config.lifespan not in {"auto", "on", "off"}:
        raise ConfigError(f"invalid lifespan mode: {config.lifespan!r}")
    if config.max_body_size <= 0:
        raise ConfigError("max_body_size must be positive")
    if config.max_header_size <= 0:
        raise ConfigError("max_header_size must be positive")
    if config.read_timeout <= 0 or config.write_timeout <= 0 or config.shutdown_timeout <= 0:
        raise ConfigError("timeouts must be positive")
    for listener in config.listeners:
        if listener.kind in {"tcp", "udp"}:
            if not listener.host:
                raise ConfigError(f"{listener.kind} listener host cannot be empty")
            if listener.port < 0 or listener.port > 65535:
                raise ConfigError(f"invalid {listener.kind.upper()} port: {listener.port}")
        elif listener.kind in {"unix", "pipe"}:
            if not listener.path:
                raise ConfigError(f"{listener.kind} listener requires a path")
        elif listener.kind != "inproc":
            raise ConfigError(f"unsupported listener kind: {listener.kind!r}")
        if listener.ssl_certfile and not listener.ssl_keyfile:
            raise ConfigError("ssl_keyfile is required when ssl_certfile is set")
        if listener.ssl_keyfile and not listener.ssl_certfile:
            raise ConfigError("ssl_certfile is required when ssl_keyfile is set")
        bad_versions = [v for v in listener.http_versions if v not in {"1.1", "2", "3"}]
        if bad_versions:
            raise ConfigError(f"unsupported http_versions: {bad_versions!r}")
        bad_protocols = [v for v in listener.enabled_protocols if v not in _ALLOWED_PROTOCOLS]
        if bad_protocols:
            raise ConfigError(f"unsupported listener protocols: {bad_protocols!r}")
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
