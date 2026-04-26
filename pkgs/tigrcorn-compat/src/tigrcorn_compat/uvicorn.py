from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompatProfile:
    server_name: str
    boundary: str
    http1: bool
    http2: bool
    websocket: bool
    lifespan: bool


UVICORN_COMPAT = CompatProfile(
    server_name='uvicorn',
    boundary='ASGI3 callable(scope, receive, send)',
    http1=True,
    http2=False,
    websocket=True,
    lifespan=True,
)
