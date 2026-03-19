from __future__ import annotations

from .defaults import default_config
from .model import ListenerConfig, ServerConfig
from .normalize import normalize_config
from .validate import validate_config


def build_config(
    *,
    app: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool = False,
    http_versions: list[str] | None = None,
    websocket: bool = True,
    enable_h2c: bool = True,
    max_body_size: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool = False,
    pipe_mode: str = "rawframed",
) -> ServerConfig:
    config = default_config()
    config.app = app
    config.lifespan = lifespan  # type: ignore[assignment]
    config.log_level = log_level
    config.access_log = access_log
    config.enable_h2c = enable_h2c
    if max_body_size is not None:
        config.max_body_size = max_body_size
    if uds and transport == "tcp":
        transport = "unix"
    listener = ListenerConfig(kind=transport.lower())
    if listener.kind in {"tcp", "udp"}:
        listener.host = host
        listener.port = port
    if listener.kind in {"unix", "pipe"}:
        listener.path = uds
    listener.ssl_certfile = ssl_certfile
    listener.ssl_keyfile = ssl_keyfile
    listener.ssl_ca_certs = ssl_ca_certs
    listener.ssl_require_client_cert = ssl_require_client_cert
    listener.websocket = websocket
    listener.pipe_mode = pipe_mode  # type: ignore[assignment]
    if protocols is not None:
        listener.protocols = list(protocols)
    if http_versions is not None:
        listener.http_versions = list(http_versions)
    if quic_secret is not None:
        listener.quic_secret = quic_secret
    listener.quic_require_retry = quic_require_retry
    config.listeners = [listener]
    normalize_config(config)
    validate_config(config)
    return config
