from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import parse_qs


JSON_HEADERS = [
    (b"content-type", b"application/json; charset=utf-8"),
    (b"access-control-allow-origin", b"*"),
    (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
    (b"access-control-allow-headers", b"content-type, x-demo-token"),
    (b"cache-control", b"no-store"),
]

TEXT_HEADERS = [
    (b"content-type", b"text/plain; charset=utf-8"),
    (b"access-control-allow-origin", b"*"),
    (b"cache-control", b"no-store"),
]


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin1"): value.decode("latin1")
        for key, value in scope.get("headers", [])
    }


async def _read_body(receive) -> tuple[bytes, int, bool]:
    body = bytearray()
    chunks = 0
    disconnected = False
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            disconnected = True
            break
        if message["type"] != "http.request":
            continue
        chunks += 1
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return bytes(body), chunks, disconnected


async def _json(send, payload: dict[str, Any], status: int = 200) -> None:
    await send({"type": "http.response.start", "status": status, "headers": JSON_HEADERS})
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps(payload, indent=2).encode("utf-8"),
            "more_body": False,
        }
    )


async def _text(send, body: bytes, *, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": headers or TEXT_HEADERS,
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def app(scope: dict[str, Any], receive, send) -> None:
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        raise RuntimeError("http11 demo only accepts ASGI HTTP scopes")

    method = scope.get("method", "GET")
    path = scope.get("path", "/")
    query = parse_qs(scope.get("query_string", b"").decode("utf-8", "replace"))

    if method == "OPTIONS":
        await _json(send, {"ok": True})
        return

    if path == "/":
        await _json(
            send,
            {
                "name": "tigrcorn HTTP/1.1 ASGI3 demo",
                "routes": ["/inspect", "/echo", "/stream", "/trailers", "/early-hints"],
                "try": "Open the UIX client and run the prepared experiments.",
            },
        )
        return

    if path == "/inspect":
        await _read_body(receive)
        await _json(
            send,
            {
                "method": method,
                "path": path,
                "http_version": scope.get("http_version"),
                "scheme": scope.get("scheme"),
                "client": scope.get("client"),
                "server": scope.get("server"),
                "root_path": scope.get("root_path"),
                "headers": _headers(scope),
                "extensions": sorted(scope.get("extensions", {}).keys()),
            },
        )
        return

    if path == "/echo":
        body, chunks, disconnected = await _read_body(receive)
        await _json(
            send,
            {
                "method": method,
                "http_version": scope.get("http_version"),
                "request_chunks_seen": chunks,
                "request_disconnected": disconnected,
                "request_headers": _headers(scope),
                "body_size": len(body),
                "body_preview": body[:512].decode("utf-8", "replace"),
            },
        )
        return

    if path == "/stream":
        await _read_body(receive)
        count = int(query.get("count", ["5"])[0])
        count = max(1, min(count, 20))
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": TEXT_HEADERS
                + [
                    (b"x-demo-stream", b"chunked-response"),
                    (b"x-accel-buffering", b"no"),
                ],
            }
        )
        for index in range(count):
            line = f"chunk {index + 1}/{count} at {time.time():.3f}\n".encode("utf-8")
            await send({"type": "http.response.body", "body": line, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        return

    if path == "/trailers":
        await _read_body(receive)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": TEXT_HEADERS
                + [
                    (b"trailer", b"x-demo-checksum, x-demo-complete"),
                    (b"x-demo-trailers", b"announced"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"body sent before HTTP/1.1 trailers\n",
                "more_body": True,
            }
        )
        await send(
            {
                "type": "http.response.trailers",
                "trailers": [
                    (b"x-demo-checksum", b"sha256-demo-value"),
                    (b"x-demo-complete", b"true"),
                ],
            }
        )
        return

    if path == "/early-hints":
        await _read_body(receive)
        await send(
            {
                "type": "http.response.start",
                "status": 103,
                "headers": [
                    (b"link", b"</style.css>; rel=preload; as=style"),
                    (b"link", b"</main.js>; rel=preload; as=script"),
                ],
            }
        )
        await _text(send, b"final response after HTTP 103 Early Hints\n")
        return

    await _json(send, {"error": "not found", "path": path}, status=404)
