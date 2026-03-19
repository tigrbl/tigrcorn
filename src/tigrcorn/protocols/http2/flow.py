from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from tigrcorn.protocols.http2.state import FlowWindow


@dataclass(slots=True)
class FlowWaiter:
    window: FlowWindow
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        if self.window.available > 0:
            self._event.set()

    def notify(self) -> None:
        if self.window.available > 0:
            self._event.set()

    async def wait(self) -> None:
        while self.window.available <= 0:
            self._event.clear()
            await self._event.wait()
