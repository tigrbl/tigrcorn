from __future__ import annotations


def websocket_denial_extension() -> dict:
    return {'websocket.http.response': {}}
