from __future__ import annotations

import asyncio
from typing import cast

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ServerConfig
from tigrcorn.server.app_loader import load_app
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.server.signals import install_signal_handlers
from tigrcorn.types import ASGIApp


async def serve(
    app: ASGIApp,
    *,
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
    config: ServerConfig | None = None,
) -> None:
    if config is None:
        config = build_config(
            host=host,
            port=port,
            uds=uds,
            transport=transport,
            lifespan=lifespan,
            log_level=log_level,
            access_log=access_log,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            ssl_ca_certs=ssl_ca_certs,
            ssl_require_client_cert=ssl_require_client_cert,
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
    app_target: str,
    *,
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
    factory: bool = False,
) -> None:
    app = load_app(app_target, factory=factory)
    await serve(
        cast(ASGIApp, app),
        host=host,
        port=port,
        uds=uds,
        transport=transport,
        lifespan=lifespan,
        log_level=log_level,
        access_log=access_log,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_ca_certs=ssl_ca_certs,
        ssl_require_client_cert=ssl_require_client_cert,
        http_versions=http_versions,
        websocket=websocket,
        enable_h2c=enable_h2c,
        max_body_size=max_body_size,
        protocols=protocols,
        quic_secret=quic_secret,
        quic_require_retry=quic_require_retry,
        pipe_mode=pipe_mode,
    )


def run(
    app: ASGIApp | str,
    *,
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
    factory: bool = False,
) -> None:
    if isinstance(app, str):
        asyncio.run(
            serve_import_string(
                app,
                host=host,
                port=port,
                uds=uds,
                transport=transport,
                lifespan=lifespan,
                log_level=log_level,
                access_log=access_log,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_ca_certs=ssl_ca_certs,
                ssl_require_client_cert=ssl_require_client_cert,
                http_versions=http_versions,
                websocket=websocket,
                enable_h2c=enable_h2c,
                max_body_size=max_body_size,
                protocols=protocols,
                quic_secret=quic_secret,
                quic_require_retry=quic_require_retry,
                pipe_mode=pipe_mode,
                factory=factory,
            )
        )
    else:
        asyncio.run(
            serve(
                app,
                host=host,
                port=port,
                uds=uds,
                transport=transport,
                lifespan=lifespan,
                log_level=log_level,
                access_log=access_log,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_ca_certs=ssl_ca_certs,
                ssl_require_client_cert=ssl_require_client_cert,
                http_versions=http_versions,
                websocket=websocket,
                enable_h2c=enable_h2c,
                max_body_size=max_body_size,
                protocols=protocols,
                quic_secret=quic_secret,
                quic_require_retry=quic_require_retry,
                pipe_mode=pipe_mode,
            )
        )
