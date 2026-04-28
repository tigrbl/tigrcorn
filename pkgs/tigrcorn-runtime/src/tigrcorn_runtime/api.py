from __future__ import annotations

import asyncio
from typing import cast

from tigrcorn_config.load import build_config
from tigrcorn_config.model import ServerConfig
from tigrcorn_runtime.server.app_loader import load_app
from tigrcorn_runtime.server.bootstrap import run_coro_with_runtime
from tigrcorn_runtime.server.runner import TigrCornServer
from tigrcorn_runtime.server.signals import install_signal_handlers
from tigrcorn_core.types import ASGIApp


async def serve(
    app: ASGIApp,
    *,
    profile: str | None = None,
    app_interface: str = "auto",
    host: str = "127.0.0.1",
    port: int = 8000,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_keyfile_password: str | bytes | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool | None = None,
    ssl_ciphers: str | None = None,
    ssl_crl: str | None = None,
    http_versions: list[str] | None = None,
    websocket: bool | None = None,
    enable_h2c: bool = False,
    max_body_size: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool | None = None,
    pipe_mode: str = "rawframed",
    config: ServerConfig | None = None,
) -> None:
    """Serve an ASGI application until shutdown is requested.

    Args:
        app: ASGI application callable to run.
        profile: Optional packaged profile name.
        app_interface: Application interface selection mode.
        host: TCP host when the TCP transport is active.
        port: TCP port when the TCP transport is active.
        uds: Unix-domain socket path when the Unix transport is active.
        transport: Listener transport family.
        lifespan: Lifespan negotiation policy.
        log_level: Runtime logging level.
        access_log: Whether access logging is enabled.
        ssl_certfile: Server certificate file path.
        ssl_keyfile: Server private key file path.
        ssl_keyfile_password: Optional private key password.
        ssl_ca_certs: Optional trust-anchor bundle for peer validation.
        ssl_require_client_cert: Whether client certificates are required.
        ssl_ciphers: Optional TLS cipher policy.
        ssl_crl: Optional certificate revocation list file.
        http_versions: Enabled HTTP protocol versions.
        websocket: Whether WebSocket handling is enabled.
        enable_h2c: Whether cleartext HTTP/2 upgrade is enabled.
        max_body_size: Optional request-body size cap.
        protocols: Enabled runtime protocol families.
        quic_secret: Optional QUIC retry/integrity secret.
        quic_require_retry: Whether QUIC retry is required.
        pipe_mode: Pipe listener framing mode.
        config: Prebuilt server configuration. Other options are used only
            when this is not supplied.

    Returns:
        None.
    """

    if config is None:
        config = build_config(
            profile=profile,
            app_interface=app_interface,
            host=host,
            port=port,
            uds=uds,
            transport=transport,
            lifespan=lifespan,
            log_level=log_level,
            access_log=access_log,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            ssl_keyfile_password=ssl_keyfile_password,
            ssl_ca_certs=ssl_ca_certs,
            ssl_require_client_cert=ssl_require_client_cert,
            ssl_ciphers=ssl_ciphers,
            ssl_crl=ssl_crl,
            http_versions=http_versions,
            websocket=websocket,
            enable_h2c=enable_h2c,
            max_body_size=max_body_size,
            protocols=protocols,
            quic_secret=quic_secret,
            quic_require_retry=quic_require_retry,
            pipe_mode=pipe_mode,
        )
    server = TigrCornServer(app=app, config=config)
    install_signal_handlers(asyncio.get_running_loop(), server.request_shutdown)
    await server.serve_forever()


async def serve_import_string(
    app_target: str | None = None,
    *,
    profile: str | None = None,
    app_interface: str = "auto",
    host: str = "127.0.0.1",
    port: int = 8000,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_keyfile_password: str | bytes | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool | None = None,
    ssl_ciphers: str | None = None,
    ssl_crl: str | None = None,
    http_versions: list[str] | None = None,
    websocket: bool | None = None,
    enable_h2c: bool = False,
    max_body_size: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool | None = None,
    pipe_mode: str = "rawframed",
    factory: bool = False,
    config: ServerConfig | None = None,
) -> None:
    """Load an ASGI application by import string and serve it.

    Args:
        app_target: Import target such as ``module:app``.
        profile: Optional packaged profile name.
        app_interface: Application interface selection mode.
        host: TCP host when the TCP transport is active.
        port: TCP port when the TCP transport is active.
        uds: Unix-domain socket path when the Unix transport is active.
        transport: Listener transport family.
        lifespan: Lifespan negotiation policy.
        log_level: Runtime logging level.
        access_log: Whether access logging is enabled.
        ssl_certfile: Server certificate file path.
        ssl_keyfile: Server private key file path.
        ssl_keyfile_password: Optional private key password.
        ssl_ca_certs: Optional trust-anchor bundle for peer validation.
        ssl_require_client_cert: Whether client certificates are required.
        ssl_ciphers: Optional TLS cipher policy.
        ssl_crl: Optional certificate revocation list file.
        http_versions: Enabled HTTP protocol versions.
        websocket: Whether WebSocket handling is enabled.
        enable_h2c: Whether cleartext HTTP/2 upgrade is enabled.
        max_body_size: Optional request-body size cap.
        protocols: Enabled runtime protocol families.
        quic_secret: Optional QUIC retry/integrity secret.
        quic_require_retry: Whether QUIC retry is required.
        pipe_mode: Pipe listener framing mode.
        factory: Whether the import target is an application factory.
        config: Prebuilt server configuration. Its application target is used
            when ``app_target`` is not supplied.

    Returns:
        None.

    Raises:
        ValueError: If no import target is supplied by arguments or config.
    """

    if config is not None:
        app_target = app_target or config.app.target
        factory = config.app.factory if factory is False else factory
    if app_target is None:
        raise ValueError("app_target is required when config.app.target is not set")
    app_dir = config.app.app_dir if config is not None else None
    if app_dir is None:
        app = load_app(app_target, factory=factory)
    else:
        app = load_app(app_target, factory=factory, app_dir=app_dir)
    await serve(
        cast(ASGIApp, app),
        profile=profile,
        app_interface=app_interface,
        host=host,
        port=port,
        uds=uds,
        transport=transport,
        lifespan=lifespan,
        log_level=log_level,
        access_log=access_log,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        ssl_require_client_cert=ssl_require_client_cert,
        ssl_ciphers=ssl_ciphers,
        ssl_crl=ssl_crl,
        http_versions=http_versions,
        websocket=websocket,
        enable_h2c=enable_h2c,
        max_body_size=max_body_size,
        protocols=protocols,
        quic_secret=quic_secret,
        quic_require_retry=quic_require_retry,
        pipe_mode=pipe_mode,
        config=config,
    )


def run(
    app: ASGIApp | str,
    *,
    profile: str | None = None,
    app_interface: str = "auto",
    host: str = "127.0.0.1",
    port: int = 8000,
    uds: str | None = None,
    transport: str = "tcp",
    lifespan: str = "auto",
    log_level: str = "info",
    access_log: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ssl_keyfile_password: str | bytes | None = None,
    ssl_ca_certs: str | None = None,
    ssl_require_client_cert: bool | None = None,
    ssl_ciphers: str | None = None,
    ssl_crl: str | None = None,
    http_versions: list[str] | None = None,
    websocket: bool | None = None,
    enable_h2c: bool = False,
    max_body_size: int | None = None,
    protocols: list[str] | None = None,
    quic_secret: bytes | None = None,
    quic_require_retry: bool | None = None,
    pipe_mode: str = "rawframed",
    factory: bool = False,
    config: ServerConfig | None = None,
) -> None:
    """Run an ASGI application or import target from synchronous code.

    Args:
        app: ASGI application callable or import target.
        profile: Optional packaged profile name.
        app_interface: Application interface selection mode.
        host: TCP host when the TCP transport is active.
        port: TCP port when the TCP transport is active.
        uds: Unix-domain socket path when the Unix transport is active.
        transport: Listener transport family.
        lifespan: Lifespan negotiation policy.
        log_level: Runtime logging level.
        access_log: Whether access logging is enabled.
        ssl_certfile: Server certificate file path.
        ssl_keyfile: Server private key file path.
        ssl_keyfile_password: Optional private key password.
        ssl_ca_certs: Optional trust-anchor bundle for peer validation.
        ssl_require_client_cert: Whether client certificates are required.
        ssl_ciphers: Optional TLS cipher policy.
        ssl_crl: Optional certificate revocation list file.
        http_versions: Enabled HTTP protocol versions.
        websocket: Whether WebSocket handling is enabled.
        enable_h2c: Whether cleartext HTTP/2 upgrade is enabled.
        max_body_size: Optional request-body size cap.
        protocols: Enabled runtime protocol families.
        quic_secret: Optional QUIC retry/integrity secret.
        quic_require_retry: Whether QUIC retry is required.
        pipe_mode: Pipe listener framing mode.
        factory: Whether a string import target is an application factory.
        config: Prebuilt server configuration. Its process runtime selects
            the async backend when supplied.

    Returns:
        None.
    """

    runtime = config.process.runtime if config is not None else 'auto'
    if isinstance(app, str):
        run_coro_with_runtime(
            lambda: serve_import_string(
                app,
                profile=profile,
                app_interface=app_interface,
                host=host,
                port=port,
                uds=uds,
                transport=transport,
                lifespan=lifespan,
                log_level=log_level,
                access_log=access_log,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_keyfile_password=ssl_keyfile_password,
                ssl_ca_certs=ssl_ca_certs,
                ssl_require_client_cert=ssl_require_client_cert,
                ssl_ciphers=ssl_ciphers,
                ssl_crl=ssl_crl,
                http_versions=http_versions,
                websocket=websocket,
                enable_h2c=enable_h2c,
                max_body_size=max_body_size,
                protocols=protocols,
                quic_secret=quic_secret,
                quic_require_retry=quic_require_retry,
                pipe_mode=pipe_mode,
                factory=factory,
                config=config,
            ),
            runtime=runtime,
        )
    else:
        run_coro_with_runtime(
            lambda: serve(
                app,
                profile=profile,
                app_interface=app_interface,
                host=host,
                port=port,
                uds=uds,
                transport=transport,
                lifespan=lifespan,
                log_level=log_level,
                access_log=access_log,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_keyfile_password=ssl_keyfile_password,
                ssl_ca_certs=ssl_ca_certs,
                ssl_require_client_cert=ssl_require_client_cert,
                ssl_ciphers=ssl_ciphers,
                ssl_crl=ssl_crl,
                http_versions=http_versions,
                websocket=websocket,
                enable_h2c=enable_h2c,
                max_body_size=max_body_size,
                protocols=protocols,
                quic_secret=quic_secret,
                quic_require_retry=quic_require_retry,
                pipe_mode=pipe_mode,
                config=config,
            ),
            runtime=runtime,
        )
