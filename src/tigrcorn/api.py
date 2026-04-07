from __future__ import annotations

import asyncio
from typing import cast

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ServerConfig
from tigrcorn.server.app_loader import load_app
from tigrcorn.server.bootstrap import run_coro_with_runtime
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.server.signals import install_signal_handlers
from tigrcorn.types import ASGIApp


async def serve(
    app: ASGIApp,
    *,
    profile: str | None = None,
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
    if config is None:
        config = build_config(
            profile=profile,
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
    runtime = config.process.runtime if config is not None else 'auto'
    if isinstance(app, str):
        run_coro_with_runtime(
            lambda: serve_import_string(
                app,
                profile=profile,
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
