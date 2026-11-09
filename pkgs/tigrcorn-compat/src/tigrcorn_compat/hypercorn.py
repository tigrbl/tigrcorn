from __future__ import annotations

from .uvicorn import CompatProfile


HYPERCORN_COMPAT = CompatProfile(
    server_name='hypercorn',
    boundary='ASGI3 callable(scope, receive, send)',
    http1=True,
    http2=True,
    websocket=True,
    lifespan=True,
)
