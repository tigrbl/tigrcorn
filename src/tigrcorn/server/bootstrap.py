from __future__ import annotations

import asyncio
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from tigrcorn.config.load import build_config, config_from_mapping, config_to_dict
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.server.app_loader import load_app
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.server.signals import install_signal_handlers
from tigrcorn.transports.tcp.socketopts import configure_socket
from tigrcorn.transports.udp.socketopts import configure_udp_socket


def bootstrap(app_target: str, **kwargs) -> TigrCornServer:
    config = build_config(app=app_target, **kwargs)
    app = load_app(app_target, factory=bool(kwargs.get('factory', False)))
    return TigrCornServer(app=app, config=config)


def _socket_for_listener(listener: ListenerConfig) -> socket.socket | None:
    if listener.kind not in {'tcp', 'udp', 'unix'} or listener.fd is not None or listener.endpoint:
        return None
    if listener.kind == 'unix':
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        path = Path(listener.path or '')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        sock.bind(str(path))
        sock.listen(listener.backlog)
        sock.setblocking(False)
        sock.set_inheritable(True)
        return sock
    family = socket.AF_INET6 if ':' in listener.host else socket.AF_INET
    if listener.kind == 'tcp':
        sock = socket.socket(family, socket.SOCK_STREAM)
        if listener.reuse_address:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if listener.reuse_port and hasattr(socket, 'SO_REUSEPORT'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind((listener.host, listener.port))
        sock.listen(listener.backlog)
        sock.setblocking(False)
        sock.set_inheritable(True)
        configure_socket(sock, nodelay=listener.nodelay)
        return sock
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if listener.reuse_port and hasattr(socket, 'SO_REUSEPORT'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((listener.host, listener.port))
    sock.setblocking(False)
    sock.set_inheritable(True)
    configure_udp_socket(sock)
    return sock


def prebind_listener_sockets(config: ServerConfig) -> list[socket.socket]:
    bound: list[socket.socket] = []
    for listener in config.listeners:
        sock = _socket_for_listener(listener)
        if sock is None:
            continue
        listener.fd = sock.fileno()
        bound.append(sock)
    return bound


def config_payload(config: ServerConfig) -> dict[str, Any]:
    return deepcopy(config_to_dict(config))


async def serve_from_config(config: ServerConfig) -> None:
    app_target = config.app.target
    if not app_target:
        raise ValueError('config.app.target is required')
    app = load_app(app_target, factory=config.app.factory, app_dir=config.app.app_dir)
    server = TigrCornServer(app=app, config=config)
    install_signal_handlers(asyncio.get_running_loop(), server.request_shutdown)
    await server.serve_forever()


def run_worker_from_config_payload(payload: Mapping[str, Any]) -> None:
    config = config_from_mapping(payload)
    asyncio.run(serve_from_config(config))
