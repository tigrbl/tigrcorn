from __future__ import annotations


class _WebSocketCloseSignal(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
