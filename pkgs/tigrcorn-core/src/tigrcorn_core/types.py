from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
Headers = list[tuple[bytes, bytes]]
Address = tuple[str, int]
MaybeAddress = tuple[str, int | None]


@runtime_checkable
class StreamReaderLike(Protocol):
    async def read(self, n: int = -1) -> bytes: ...
    async def readexactly(self, n: int) -> bytes: ...
    async def readuntil(self, separator: bytes = b"\n") -> bytes: ...


__all__ = [
    "ASGIApp",
    "Address",
    "Headers",
    "MaybeAddress",
    "Message",
    "Receive",
    "Scope",
    "Send",
    "StreamReaderLike",
]
