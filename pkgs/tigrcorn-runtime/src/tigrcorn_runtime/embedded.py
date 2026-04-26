from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tigrcorn_runtime.app_interfaces import resolve_app_dispatch
from tigrcorn_config.model import ServerConfig
from tigrcorn_runtime.server.runner import TigrCornServer
from tigrcorn_core.types import ASGIApp


@dataclass(slots=True)
class EmbeddedServer:
    """Small async helper for embedding tigrcorn inside a larger application.

    Public contract:

    - ``start()`` is idempotent and returns the underlying ``TigrCornServer``
    - ``close()`` is a no-op before startup and closes the running server after
      startup
    - the async context-manager surface calls ``start()`` on entry and
      ``close()`` on exit
    - ``listeners`` and ``bound_endpoints()`` expose the currently bound
      listener/runtime endpoints
    """

    app: ASGIApp
    config: ServerConfig
    server: TigrCornServer | None = field(default=None, init=False)

    async def start(self) -> TigrCornServer:
        resolve_app_dispatch(self.app, self.config.app.interface)
        if self.server is None:
            self.server = TigrCornServer(self.app, self.config)
        await self.server.start()
        return self.server

    async def close(self) -> None:
        if self.server is None:
            return
        await self.server.close()

    async def __aenter__(self) -> 'EmbeddedServer':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def listeners(self) -> list[Any]:
        if self.server is None:
            return []
        return list(self.server._listeners)

    def bound_endpoints(self) -> list[Any]:
        if self.server is None:
            return []
        endpoints: list[Any] = []
        for listener in self.server._listeners:
            server = getattr(listener, 'server', None)
            if server is not None and getattr(server, 'sockets', None):
                endpoints.extend(sock.getsockname() for sock in server.sockets)
                continue
            transport = getattr(listener, 'transport', None)
            if transport is not None:
                sockname = transport.get_extra_info('sockname')
                if sockname is not None:
                    endpoints.append(sockname)
                    continue
            path = getattr(listener, 'path', None)
            if path:
                endpoints.append(path)
        return endpoints


__all__ = ['EmbeddedServer']
