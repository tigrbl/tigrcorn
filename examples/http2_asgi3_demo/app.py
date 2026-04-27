from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs


def _headers(scope: dict[str, object]) -> dict[str, str]:
    return {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


async def _read_body(receive) -> bytes:
    chunks = bytearray()
    while True:
        event = await receive()
        if event["type"] != "http.request":
            continue
        chunks.extend(event.get("body", b""))
        if not event.get("more_body", False):
            return bytes(chunks)


async def _json(send, payload: dict[str, object], *, status: int = 200) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _stream(send, scope: dict[str, object]) -> None:
    query = parse_qs(scope.get("query_string", b"").decode("ascii", "ignore"))
    count = max(1, min(int(query.get("chunks", ["5"])[0]), 20))
    delay = max(0.0, min(float(query.get("delay", ["0.15"])[0]), 2.0))
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/x-ndjson; charset=utf-8")],
        }
    )
    for index in range(count):
        chunk = {
            "chunk": index + 1,
            "http_version": scope.get("http_version"),
            "stream_path": scope.get("path"),
            "ts": datetime.now(UTC).isoformat(),
        }
        await send(
            {
                "type": "http.response.body",
                "body": (json.dumps(chunk, sort_keys=True) + "\n").encode("utf-8"),
                "more_body": True,
            }
        )
        await asyncio.sleep(delay)
    await send({"type": "http.response.body", "body": b"", "more_body": False})


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        raise RuntimeError("HTTP/2 ASGI3 demo only accepts HTTP scopes")

    path = scope.get("path", "/")
    if path == "/stream":
        await _stream(send, scope)
        return

    body = await _read_body(receive)
    payload = {
        "message": "tigrcorn HTTP/2 ASGI3 demo",
        "method": scope.get("method"),
        "path": path,
        "query_string": scope.get("query_string", b"").decode("ascii", "ignore"),
        "http_version": scope.get("http_version"),
        "scheme": scope.get("scheme"),
        "client": scope.get("client"),
        "server": scope.get("server"),
        "headers": _headers(scope),
        "body_text": body.decode("utf-8", "replace"),
        "body_size": len(body),
        "observed_at": datetime.now(UTC).isoformat(),
    }
    await _json(send, payload)
