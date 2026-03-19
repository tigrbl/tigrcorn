from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable


class BaseListener(ABC):
    @abstractmethod
    async def start(self, client_connected_cb: Callable[..., Awaitable[None]]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
