from __future__ import annotations

import json
import os
from typing import Any


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _scope_snapshot(scope: dict[str, Any]) -> dict[str, Any]:
    extensions = scope.get("extensions") or {}
    security = extensions.get("tigrcorn.security") or {}
    transport = extensions.get("tigrcorn.transport") or {}
    unit = extensions.get("tigrcorn.unit") or {}
    return {
        "type": scope.get("type"),
        "path": scope.get("path"),
        "security": {
            "tls": security.get("tls"),
            "mtls": security.get("mtls"),
            "alpn": security.get("alpn"),
            "sni": security.get("sni"),
            "peer_certificate": security.get("peer_certificate"),
        },
        "transport": transport,
        "unit": unit,
        "extension_keys": sorted(extensions),
    }


def _require_mtls() -> bool:
    return os.environ.get("TIGRCORN_DEMO_REQUIRE_MTLS", "").lower() in {"1", "true", "yes", "on"}


async def _http(scope: dict[str, Any], receive, send) -> None:
    body = _json_bytes({"ok": True, "scope": _scope_snapshot(scope)})
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _webtransport(scope: dict[str, Any], receive, send) -> None:
    extensions = scope.get("extensions") or {}
    security = extensions.get("tigrcorn.security") or {}
    unit = extensions.get("tigrcorn.unit") or {}
    session_id = unit.get("session_id") or scope.get("session_id") or "demo-session"

    if _require_mtls() and not security.get("mtls"):
        await send({"type": "webtransport.close", "session_id": session_id, "code": 403, "reason": "mTLS required"})
        return

    await send({"type": "webtransport.accept", "session_id": session_id})
    await send(
        {
            "type": "webtransport.datagram.send",
            "session_id": session_id,
            "datagram_id": "hello",
            "data": _json_bytes({"event": "accepted", "scope": _scope_snapshot(scope)}),
        }
    )

    while True:
        event = await receive()
        event_type = event.get("type")

        if event_type == "webtransport.stream.receive":
            stream_id = event.get("stream_id", "stream")
            data = event.get("data", b"")
            await send(
                {
                    "type": "webtransport.stream.send",
                    "session_id": event.get("session_id", session_id),
                    "stream_id": stream_id,
                    "data": b"echo:" + data,
                    "more": False,
                }
            )
        elif event_type == "webtransport.datagram.receive":
            data = event.get("data", b"")
            await send(
                {
                    "type": "webtransport.datagram.send",
                    "session_id": event.get("session_id", session_id),
                    "datagram_id": event.get("datagram_id", "datagram"),
                    "data": b"ack:" + data,
                }
            )
        elif event_type in {"webtransport.disconnect", "webtransport.close"}:
            break


async def app(scope: dict[str, Any], receive, send) -> None:
    if scope["type"] == "webtransport":
        await _webtransport(scope, receive, send)
    elif scope["type"] == "http":
        await _http(scope, receive, send)
    else:
        raise RuntimeError(f"unsupported scope type: {scope['type']!r}")
