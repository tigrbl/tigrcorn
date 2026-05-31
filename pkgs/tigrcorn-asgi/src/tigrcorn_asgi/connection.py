from __future__ import annotations

from dataclasses import dataclass

from tigrcorn_core.types import Receive, Scope, Send


@dataclass(slots=True)
class ASGIConnection:
    scope: Scope
    receive: Receive
    send: Send
