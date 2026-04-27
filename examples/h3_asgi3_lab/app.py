from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _decode_payload(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.hex()


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
    body = _json_bytes(
        {
            "ok": True,
            "message": "Tigrcorn ASGI3 HTTP/3 lab endpoint",
            "scope": _scope_view(scope),
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


async def _webtransport(scope: dict[str, Any], receive, send) -> None:
    unit = (scope.get("extensions") or {}).get("tigrcorn.unit") or {}
    session_id = unit.get("session_id") or scope.get("session_id") or "h3-lab-session"

    await send({"type": "webtransport.accept", "session_id": session_id})
    await send(
        {
            "type": "webtransport.datagram.send",
            "session_id": session_id,
            "datagram_id": "welcome",
            "data": _json_bytes(
                {
                    "event": "accepted",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "scope": _scope_view(scope),
                }
            ),
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
                    "data": _json_bytes(
                        {
                            "event": "stream.echo",
                            "stream_id": stream_id,
                            "payload": _decode_payload(data),
                        }
                    ),
                    "more": False,
                }
            )
        elif event_type == "webtransport.datagram.receive":
            datagram_id = event.get("datagram_id", "datagram")
            data = event.get("data", b"")
            await send(
                {
                    "type": "webtransport.datagram.send",
                    "session_id": event.get("session_id", session_id),
                    "datagram_id": datagram_id,
                    "data": _json_bytes(
                        {
                            "event": "datagram.ack",
                            "datagram_id": datagram_id,
                            "payload": _decode_payload(data),
                        }
                    ),
                }
            )
        elif event_type in {"webtransport.disconnect", "webtransport.close"}:
            break


async def app(scope: dict[str, Any], receive, send) -> None:
    if scope["type"] == "http":
        await _http(scope, receive, send)
    elif scope["type"] == "webtransport":
        await _webtransport(scope, receive, send)
    else:
        raise RuntimeError(f"unsupported scope type: {scope['type']!r}")

