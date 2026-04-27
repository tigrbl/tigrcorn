from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tigrcorn_asgi.events.lifespan import lifespan_shutdown, lifespan_startup
from tigrcorn_asgi.receive import LifespanReceive
from tigrcorn_asgi.scopes.lifespan import build_lifespan_scope
from tigrcorn_asgi.send import LifespanSend
from tigrcorn_core.errors import TigrCornError
from tigrcorn_core.types import ASGIApp


class LifespanError(TigrCornError):
    pass


@dataclass(slots=True)
class LifespanManager:
    app: ASGIApp
    mode: str = "auto"
    timeout: float = 10.0
    started: bool = False
    _receive: LifespanReceive | None = None
    _send: LifespanSend | None = None
    _task: asyncio.Task | None = None

    async def startup(self) -> None:
        if self.mode == "off":
            return
        receive = LifespanReceive()
        send = LifespanSend()
        scope = build_lifespan_scope()

        async def runner() -> None:
            await self.app(scope, receive, send)

        task = asyncio.create_task(runner(), name="tigrcorn-lifespan")
        self._receive = receive
        self._send = send
        self._task = task
        await receive.put(lifespan_startup())
        try:
            message = await asyncio.wait_for(send.get(), timeout=self.timeout)
        except Exception as exc:
            task.cancel()
            if self.mode == "auto":
                self._task = None
                self._receive = None
                self._send = None
                return
            raise LifespanError("lifespan startup did not complete") from exc

        if message["type"] == "lifespan.startup.complete":
            self.started = True
            return
        if message["type"] == "lifespan.startup.failed":
            task.cancel()
            raise LifespanError(str(message.get("message", "lifespan startup failed")))
        if self.mode == "auto":
            task.cancel()
            self._task = None
            self._receive = None
            self._send = None
            return
        raise LifespanError(f"unexpected lifespan startup message: {message!r}")

    async def shutdown(self) -> None:
        if self.mode == "off":
            return
        if not self.started:
            if self._task is not None:
                self._task.cancel()
            return
        assert self._receive is not None and self._send is not None
        await self._receive.put(lifespan_shutdown())
        message = await asyncio.wait_for(self._send.get(), timeout=self.timeout)
        if message["type"] == "lifespan.shutdown.failed":
            raise LifespanError(str(message.get("message", "lifespan shutdown failed")))
        if message["type"] != "lifespan.shutdown.complete":
            raise LifespanError(f"unexpected lifespan shutdown message: {message!r}")
        if self._task is not None:
            await asyncio.wait({self._task}, timeout=self.timeout)
