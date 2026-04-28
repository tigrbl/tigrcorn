from __future__ import annotations

import asyncio
from contextlib import suppress
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs


SERVER_STARTED_AT = datetime.now(UTC)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


async def _send_json_response(send, status: int, payload: dict[str, Any]) -> None:
    body = _json_bytes(payload)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"cache-control", b"no-store"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _http(scope: dict[str, Any], _receive, send) -> None:
    path = scope.get("path", "/")
    if path in {"/", "/health"}:
        await _send_json_response(
            send,
            200,
            {
                "ok": True,
                "server": "tigrcorn",
                "interface": "asgi3",
                "websocket_path": "/ws",
                "wss_url": "wss://localhost:8443/ws",
                "started_at": SERVER_STARTED_AT.isoformat(),
                "scope_extensions": sorted((scope.get("extensions") or {}).keys()),
            },
        )
        return
    await _send_json_response(send, 404, {"ok": False, "error": "not found", "path": path})


async def _websocket(scope: dict[str, Any], receive, send) -> None:
    query = parse_qs((scope.get("query_string") or b"").decode("utf-8", "replace"))
    room = (query.get("room") or ["lab"])[0] or "lab"
    client_name = (query.get("name") or ["browser"])[0] or "browser"

    connect = await receive()
    if connect["type"] != "websocket.connect":
        return

    await send(
        {
            "type": "websocket.accept",
            "subprotocol": "tigrcorn.lab.v1",
            "headers": [(b"x-tigrcorn-demo", b"wss-asgi3")],
        }
    )
    await send(
        {
            "type": "websocket.send",
            "text": json.dumps(
                {
                    "kind": "ready",
                    "room": room,
                    "client": client_name,
                    "server_time": datetime.now(UTC).isoformat(),
                    "extensions": sorted((scope.get("extensions") or {}).keys()),
                }
            ),
        }
    )

    ticker = asyncio.create_task(_tick(send))
    count = 0
    try:
        while True:
            event = await receive()
            event_type = event["type"]
            if event_type == "websocket.disconnect":
                return
            if event_type != "websocket.receive":
                continue
            count += 1
            if event.get("text") is not None:
                text = event["text"]
                if text.strip().lower() == "/close":
                    await send({"type": "websocket.close", "code": 1000, "reason": "client requested close"})
                    return
                await send(
                    {
                        "type": "websocket.send",
                        "text": json.dumps(
                            {
                                "kind": "echo",
                                "mode": "text",
                                "room": room,
                                "client": client_name,
                                "count": count,
                                "payload": text,
                                "server_time": datetime.now(UTC).isoformat(),
                            }
                        ),
                    }
                )
            elif event.get("bytes") is not None:
                payload = event["bytes"]
                await send(
                    {
                        "type": "websocket.send",
                        "text": json.dumps(
                            {
                                "kind": "echo",
                                "mode": "bytes",
                                "room": room,
                                "client": client_name,
                                "count": count,
                                "bytes": len(payload),
                                "server_time": datetime.now(UTC).isoformat(),
                            }
                        ),
                    }
                )
    finally:
        ticker.cancel()
        with suppress(asyncio.CancelledError):
            await ticker


async def _tick(send) -> None:
    while True:
        await asyncio.sleep(5)
        await send(
            {
                "type": "websocket.send",
                "text": json.dumps({"kind": "tick", "server_time": datetime.now(UTC).isoformat()}),
            }
        )


async def app(scope, receive, send) -> None:
    scope_type = scope["type"]
    if scope_type == "lifespan":
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope_type == "http":
        await _http(scope, receive, send)
        return
    if scope_type == "websocket":
        await _websocket(scope, receive, send)
        return
    raise RuntimeError(f"unsupported ASGI scope type: {scope_type!r}")
