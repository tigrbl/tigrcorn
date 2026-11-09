from __future__ import annotations

import asyncio
import contextlib
import os
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from tigrcorn_config.load import build_config, config_from_mapping, config_to_dict
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_core.constants import SUPPORTED_RUNTIMES
from tigrcorn_runtime.server.app_loader import load_app
from tigrcorn_runtime.server.runner import TigrCornServer
from tigrcorn_static.static import mount_static_app
from tigrcorn_core.types import ASGIApp
from tigrcorn_runtime.server.signals import install_signal_handlers
from tigrcorn_transports.tcp.socketopts import configure_socket
from tigrcorn_transports.udp.socketopts import configure_udp_socket


def bootstrap(app_target: str, **kwargs) -> TigrCornServer:
    config = build_config(app=app_target, **kwargs)
    app = load_app(app_target, factory=bool(kwargs.get('factory', False)))
    if config.static.mount:
        app = mount_static_app(
            app,
            route=config.static.route or '/',
            directory=config.static.mount,
            dir_to_file=config.static.dir_to_file,
            index_file=config.static.index_file,
            expires=config.static.expires,
            apply_content_coding=True,
            content_coding_policy=config.http.content_coding_policy,
            content_codings=tuple(config.http.content_codings),
        )
    return TigrCornServer(app=app, config=config)


def load_configured_app(config: ServerConfig) -> ASGIApp | None:
    app: ASGIApp | None = None
    if config.app.target:
        app = load_app(config.app.target, factory=config.app.factory, app_dir=config.app.app_dir)
    if config.static.mount:
        app = mount_static_app(
            app,
            route=config.static.route or '/',
            directory=config.static.mount,
            dir_to_file=config.static.dir_to_file,
            index_file=config.static.index_file,
            expires=config.static.expires,
            apply_content_coding=True,
            content_coding_policy=config.http.content_coding_policy,
            content_codings=tuple(config.http.content_codings),
        )
    return app


def _resolve_unix_identity(value: str | int | None, *, group: bool) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raw = value.strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if os.name != 'posix':
        raise RuntimeError('user/group unix socket ownership controls require POSIX')
    if group:
        import grp

        return grp.getgrnam(raw).gr_gid
    import pwd

    return pwd.getpwnam(raw).pw_uid


def _apply_unix_socket_metadata(listener: ListenerConfig) -> None:
    if listener.kind != 'unix' or not listener.path or os.name != 'posix':
        return
    uid = _resolve_unix_identity(listener.user, group=False)
    gid = _resolve_unix_identity(listener.group, group=True)
    path = Path(listener.path)
    if uid is not None or gid is not None:
        os.chown(path, -1 if uid is None else uid, -1 if gid is None else gid)
    if listener.umask is not None:
        path.chmod(0o777 & ~listener.umask)


def _socket_for_listener(listener: ListenerConfig) -> socket.socket | None:
    if listener.kind not in {'tcp', 'udp', 'unix'} or listener.fd is not None or listener.endpoint:
        return None
    if listener.kind == 'unix':
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        path = Path(listener.path or '')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        previous_umask = None
        if listener.umask is not None and os.name == 'posix':
            previous_umask = os.umask(listener.umask)
        try:
            sock.bind(str(path))
        finally:
            if previous_umask is not None:
                os.umask(previous_umask)
        _apply_unix_socket_metadata(listener)
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


async def serve_from_config(config: ServerConfig, *, ready_pipe: Any | None = None) -> None:
    app = load_configured_app(config)
    if app is None:
        raise ValueError('config.app.target or config.static.mount is required')
    server = TigrCornServer(app=app, config=config)
    install_signal_handlers(asyncio.get_running_loop(), server.request_shutdown)
    await server.start()
    if ready_pipe is not None:
        with contextlib.suppress(Exception):
            ready_pipe.send('ready')
            ready_pipe.close()
    try:
        await server._should_exit.wait()
    finally:
        await server.close()



def runtime_compatibility_matrix() -> dict[str, dict[str, object]]:
    """Return the public runtime compatibility contract for the supported runtime surface."""
    matrix = {
        'auto': {
            'implemented': True,
            'strategy': 'prefers uvloop when installed, otherwise asyncio',
            'requires': [],
        },
        'asyncio': {
            'implemented': True,
            'strategy': 'native asyncio event loop',
            'requires': [],
        },
        'uvloop': {
            'implemented': True,
            'strategy': 'uvloop event loop',
            'requires': ['uvloop'],
        },
    }
    return {name: matrix[name] for name in SUPPORTED_RUNTIMES}

def run_coro_with_runtime(factory, *, runtime: str) -> None:
    selected = runtime
    if selected == 'auto':
        try:
            import uvloop  # type: ignore[import-not-found]
        except Exception:
            selected = 'asyncio'
        else:
            selected = 'uvloop'
            uvloop.run(factory())
            return
    if selected == 'asyncio':
        asyncio.run(factory())
        return
    if selected == 'uvloop':
        try:
            import uvloop  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "runtime 'uvloop' requires the uvloop package; install tigrcorn[runtime-uvloop]"
            ) from exc
        uvloop.run(factory())
        return
    raise RuntimeError(f'unsupported runtime: {runtime!r}')


def run_config(config: ServerConfig, *, ready_pipe: Any | None = None) -> None:
    run_coro_with_runtime(lambda: serve_from_config(config, ready_pipe=ready_pipe), runtime=config.process.runtime)


def run_worker_from_config_payload(payload: Mapping[str, Any], ready_pipe: Any | None = None) -> None:
    config = config_from_mapping(payload)
    run_config(config, ready_pipe=ready_pipe)
