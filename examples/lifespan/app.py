from __future__ import annotations

import json
import mimetypes
from pathlib import Path
import time
from typing import Any


UIX_ROOT = Path(__file__).with_name("uix")

STATE: dict[str, Any] = {
    "ready": False,
    "startup_count": 0,
    "shutdown_count": 0,
    "started_at": None,
    "last_event": None,
    "request_count": 0,
    "events": [],
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
            record_event("lifespan.startup")
            print("lifespan startup complete", flush=True)
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            STATE["ready"] = False
            STATE["shutdown_count"] += 1
            STATE["last_event"] = "lifespan.shutdown"
            record_event("lifespan.shutdown")
            print("lifespan shutdown complete", flush=True)
            await send({"type": "lifespan.shutdown.complete"})
            return


async def http(scope, receive, send) -> None:
    await drain_request_body(receive)
    path = scope.get("path", "/")
    STATE["request_count"] += 1
    record_event(f"http {path}")

    if path in {"/uix", "/uix/"}:
        await serve_uix_file("index.html", send)
        return

    if path.startswith("/uix/"):
        await serve_uix_file(path.removeprefix("/uix/"), send)
        return

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
        b"GET /uix/ opens the demo console.\n"
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


async def serve_uix_file(relative_path: str, send) -> None:
    if not relative_path or relative_path.endswith("/"):
        relative_path = f"{relative_path}index.html"
    target = (UIX_ROOT / relative_path).resolve()
    if UIX_ROOT.resolve() not in target.parents and target != UIX_ROOT.resolve():
        await respond(send, b"not found\n", status=404, content_type=b"text/plain; charset=utf-8")
        return
    if not target.is_file():
        await respond(send, b"not found\n", status=404, content_type=b"text/plain; charset=utf-8")
        return
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    await respond(send, target.read_bytes(), content_type=content_type.encode("ascii"))


def record_event(name: str) -> None:
    events = STATE["events"]
    events.append({"at": time.time(), "event": name})
    del events[:-12]
