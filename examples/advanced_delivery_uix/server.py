from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import parse_qs


BODY = (
    b"Tigrcorn delivery semantics run around a normal ASGI3 app. "
    b"This payload is intentionally long enough for byte ranges, "
    b"conditional validators, and content coding experiments. "
    b"0123456789abcdefghijklmnopqrstuvwxyz"
)

JSON_HEADERS = [
    (b"content-type", b"application/json; charset=utf-8"),
    (b"access-control-allow-origin", b"*"),
    (b"access-control-allow-methods", b"GET, HEAD, POST, OPTIONS"),
    (b"access-control-allow-headers", b"content-type, if-none-match, if-match, if-modified-since, if-unmodified-since, if-range, range, accept-encoding, te, x-demo-token"),
    (b"access-control-expose-headers", b"etag, last-modified, accept-ranges, content-range, content-encoding, vary, alt-svc, trailer, x-demo-feature"),
    (b"cache-control", b"no-store"),
]

TEXT_HEADERS = [
    (b"content-type", b"text/plain; charset=utf-8"),
    (b"access-control-allow-origin", b"*"),
    (b"access-control-expose-headers", b"etag, last-modified, accept-ranges, content-range, content-encoding, vary, alt-svc, trailer, x-demo-feature"),
    (b"last-modified", b"Wed, 01 Jan 2025 00:00:00 GMT"),
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
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": JSON_HEADERS + [(b"content-length", str(len(body)).encode("ascii"))],
    })
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
        raise RuntimeError("advanced delivery UIX demo only accepts ASGI HTTP scopes")

    method = scope.get("method", "GET")
    path = scope.get("path", "/")
    query = parse_qs(scope.get("query_string", b"").decode("utf-8", "replace"))

    if method == "OPTIONS":
        await _json(send, {"ok": True})
        return

    if path == "/":
        await _read_body(receive)
        await _json(
            send,
            {
                "name": "tigrcorn advanced delivery ASGI3 lab",
                "routes": [
                    "/inspect",
                    "/resource",
                    "/trailers",
                    "/early-hints",
                    "/alt-svc",
                    "/stream",
                ],
                "features": [
                    "CONNECT relay",
                    "trailer fields",
                    "content coding",
                    "conditional requests",
                    "range requests",
                    "Early Hints",
                    "bounded Alt-Svc",
                ],
            },
        )
        return

    if path == "/inspect":
        body, chunks, disconnected = await _read_body(receive)
        await _json(
            send,
            {
                "method": method,
                "path": path,
                "query": query,
                "http_version": scope.get("http_version"),
                "scheme": scope.get("scheme"),
                "client": scope.get("client"),
                "server": scope.get("server"),
                "root_path": scope.get("root_path"),
                "request_chunks_seen": chunks,
                "request_disconnected": disconnected,
                "request_body_size": len(body),
                "headers": _headers(scope),
                "extensions": sorted(scope.get("extensions", {}).keys()),
            },
        )
        return

    if path == "/resource":
        await _read_body(receive)
        headers = TEXT_HEADERS + [
            (b"x-demo-feature", b"entity-semantics"),
            (b"cache-control", b"public, max-age=60"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": BODY, "more_body": False})
        return

    if path == "/stream":
        await _read_body(receive)
        count = max(1, min(int(query.get("count", ["5"])[0]), 20))
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": TEXT_HEADERS + [(b"x-demo-feature", b"streaming-body")],
        })
        for index in range(count):
            line = f"chunk {index + 1}/{count} at {time.time():.3f}\n".encode("utf-8")
            await send({"type": "http.response.body", "body": line, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        return

    if path == "/trailers":
        await _read_body(receive)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": TEXT_HEADERS + [
                (b"trailer", b"x-demo-checksum, x-demo-complete"),
                (b"x-demo-feature", b"trailer-fields"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"body bytes arrive before trailers\n",
            "more_body": True,
        })
        await send({
            "type": "http.response.trailers",
            "trailers": [
                (b"x-demo-checksum", b"sha256-demo-value"),
                (b"x-demo-complete", b"true"),
            ],
        })
        return

    if path == "/early-hints":
        await _read_body(receive)
        await send({
            "type": "http.response.start",
            "status": 103,
            "headers": [
                (b"link", b"</client/styles.css>; rel=preload; as=style"),
                (b"link", b"</client/main.js>; rel=preload; as=script"),
                (b"x-demo-unsafe", b"filtered-from-103"),
            ],
        })
        body = b"final response after HTTP 103 Early Hints\n"
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": TEXT_HEADERS + [(b"x-demo-feature", b"early-hints")],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})
        return

    if path == "/alt-svc":
        await _read_body(receive)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": TEXT_HEADERS + [(b"x-demo-feature", b"bounded-alt-svc")],
        })
        await send({"type": "http.response.body", "body": b"Alt-Svc is attached by Tigrcorn server configuration\n", "more_body": False})
        return

    await _json(send, {"error": "not found", "path": path}, status=404)
