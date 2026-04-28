from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WebSocketState:
    accepted: bool = False
    close_sent: bool = False
    close_received: bool = False
