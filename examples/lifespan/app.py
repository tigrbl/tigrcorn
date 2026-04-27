from __future__ import annotations

import json
import time
from typing import Any


STATE: dict[str, Any] = {
    "ready": False,
    "startup_count": 0,
    "shutdown_count": 0,
    "started_at": None,
    "last_event": None,
}


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await lifespan(receive, send)
        return
    if scope["type"] == "http":
        await http(scope, receive, send)
        return
    raise RuntimeError(f"unsupported scope type: {scope['type']}")


async def lifespan(receive, send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            STATE["ready"] = True
            STATE["startup_count"] += 1
            STATE["started_at"] = time.time()
            STATE["last_event"] = "lifespan.startup"
            print("lifespan startup complete", flush=True)
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            STATE["ready"] = False
            STATE["shutdown_count"] += 1
            STATE["last_event"] = "lifespan.shutdown"
            print("lifespan shutdown complete", flush=True)
            await send({"type": "lifespan.shutdown.complete"})
            return


async def http(scope, receive, send) -> None:
    await drain_request_body(receive)
    path = scope.get("path", "/")

    if path == "/healthz":
        body = b"ready\n" if STATE["ready"] else b"not ready\n"
        await respond(send, body, status=200 if STATE["ready"] else 503, content_type=b"text/plain; charset=utf-8")
        return

    if path == "/state":
        body = json.dumps(STATE, sort_keys=True).encode("utf-8") + b"\n"
        await respond(send, body, content_type=b"application/json")
        return

    body = (
        b"Tigrcorn ASGI3 lifespan example\n"
        b"GET /healthz returns readiness from lifespan startup.\n"
        b"GET /state returns the in-memory lifecycle counters.\n"
    )
    await respond(send, body, content_type=b"text/plain; charset=utf-8")


async def drain_request_body(receive) -> None:
    while True:
        message = await receive()
        if message["type"] != "http.request" or not message.get("more_body", False):
            return


async def respond(send, body: bytes, *, status: int = 200, content_type: bytes) -> None:
    headers = [
        (b"content-type", content_type),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body, "more_body": False})
