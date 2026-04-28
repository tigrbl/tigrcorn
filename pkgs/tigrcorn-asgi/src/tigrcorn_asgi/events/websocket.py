from __future__ import annotations


def websocket_connect() -> dict:
    return {"type": "websocket.connect"}


def websocket_receive_text(text: str) -> dict:
    return {"type": "websocket.receive", "text": text, "bytes": None}


def websocket_receive_bytes(data: bytes) -> dict:
    return {"type": "websocket.receive", "text": None, "bytes": data}


def websocket_disconnect(code: int = 1005, reason: str = "") -> dict:
    return {"type": "websocket.disconnect", "code": code, "reason": reason}
