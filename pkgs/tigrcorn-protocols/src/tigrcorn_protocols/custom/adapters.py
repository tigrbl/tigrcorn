from __future__ import annotations

from tigrcorn_asgi.events.custom import stream_receive, stream_send


def adapt_scope(scope: dict) -> dict:
    adapted = dict(scope)
    adapted.setdefault('extensions', {})
    adapted['extensions'].setdefault('tigrcorn.custom', {})
    return adapted


def adapt_inbound(payload: bytes, *, more_data: bool = False) -> dict:
    return stream_receive(payload, more_data=more_data)


def adapt_outbound(payload: bytes, *, more_data: bool = False) -> dict:
    return stream_send(payload, more_data=more_data)
