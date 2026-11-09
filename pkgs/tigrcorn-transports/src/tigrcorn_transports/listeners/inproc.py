from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from .base import BaseListener


class InProcListener(BaseListener):
    def __init__(self) -> None:
        self._callback: Callable[..., Awaitable[None]] | None = None

    async def start(self, client_connected_cb: Callable[..., Awaitable[None]]) -> None:
        self._callback = client_connected_cb

    async def dispatch(self, *args) -> None:
        if self._callback is None:
            raise RuntimeError('in-process listener has not been started')
        result = self._callback(*args)
        if inspect.isawaitable(result):
            await result

    async def close(self) -> None:
        self._callback = None
