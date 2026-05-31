from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tigrcorn.contract import asgi3_compat_scope, asgi_extension_bridge, unit_identity

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def compatibility_metadata(scope: dict[str, Any]) -> dict[str, Any]:
    compat_scope = asgi3_compat_scope(scope)
    unit = unit_identity("asgi3-example-request", family="request", binding="http")
    extensions = asgi_extension_bridge(unit=unit, capabilities={"request": ["http"]})
    return {"scope": compat_scope, "extensions": extensions}


async def app(scope: dict[str, Any], receive: Receive, send: Send) -> None:
    metadata = compatibility_metadata(scope)
    body = b"asgi3 compatibility example"

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"x-tigrcorn-interface", b"asgi3"),
            ],
            "extensions": metadata["extensions"],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})
