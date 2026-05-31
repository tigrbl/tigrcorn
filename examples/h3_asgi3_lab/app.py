from __future__ import annotations

import json
from typing import Any


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _scope_view(scope: dict[str, Any]) -> dict[str, Any]:
    extensions = scope.get("extensions") or {}
    security = extensions.get("tigrcorn.security") or {}
    transport = extensions.get("tigrcorn.transport") or {}
    unit = extensions.get("tigrcorn.unit") or {}
    return {
        "type": scope.get("type"),
        "http_version": scope.get("http_version"),
        "method": scope.get("method"),
        "path": scope.get("path"),
        "query_string": (scope.get("query_string") or b"").decode("latin1"),
        "scheme": scope.get("scheme"),
        "extensions": sorted(extensions),
        "security": {
            "tls": security.get("tls"),
            "mtls": security.get("mtls"),
            "alpn": security.get("alpn"),
            "sni": security.get("sni"),
        },
        "transport": transport,
        "unit": unit,
    }


async def _http(scope: dict[str, Any], receive, send) -> None:
    chunks: list[bytes] = []
    while True:
        event = await receive()
        if event.get("type") == "http.request":
            chunks.append(event.get("body", b""))
            if not event.get("more_body", False):
                break
        elif event.get("type") == "http.disconnect":
            break

    body = _json_bytes(
        {
            "ok": True,
            "message": "Tigrcorn ASGI3 HTTP/3 lab endpoint",
            "scope": _scope_view(scope),
            "request_body": b"".join(chunks).decode("utf-8", errors="replace"),
        }
    )
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def app(scope: dict[str, Any], receive, send) -> None:
    if scope["type"] == "http":
        await _http(scope, receive, send)
    else:
        raise RuntimeError(f"unsupported scope type: {scope['type']!r}")
