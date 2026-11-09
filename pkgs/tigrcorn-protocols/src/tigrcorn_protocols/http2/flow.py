from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from tigrcorn_protocols.http2.state import FlowWindow, MAX_FLOW_WINDOW


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


def next_adaptive_window_target(current_target: int, observed_bytes: int) -> int:
    if observed_bytes <= 0:
        return current_target
    threshold = max(1, current_target // 2)
    if observed_bytes < threshold:
        return current_target
    proposed = max(current_target * 2, observed_bytes * 2)
    return min(MAX_FLOW_WINDOW, proposed)
