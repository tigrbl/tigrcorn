from __future__ import annotations

import asyncio
import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


async def _send_json(send: Any, status: int, payload: dict[str, Any]) -> None:
    body = _json_bytes(payload)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"access-control-allow-origin", b"*"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


@dataclass
class Peer:
    id: str
    name: str
    connected_at_ms: int
    send: Any
    message_count: int = 0
    bytes_received: int = 0
    last_seen_ms: int = field(default_factory=_now_ms)


class WebSocketHub:
    def __init__(self) -> None:
        self._peers: dict[str, Peer] = {}
        self._lock = asyncio.Lock()
        self.started_at_ms = _now_ms()
        self.total_connections = 0
        self.total_messages = 0

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            peers = [
                {
                    "id": peer.id,
                    "name": peer.name,
                    "connected_at_ms": peer.connected_at_ms,
                    "message_count": peer.message_count,
                    "bytes_received": peer.bytes_received,
                    "last_seen_ms": peer.last_seen_ms,
                }
                for peer in self._peers.values()
            ]
            return {
                "started_at_ms": self.started_at_ms,
                "now_ms": _now_ms(),
                "connected": len(peers),
                "total_connections": self.total_connections,
                "total_messages": self.total_messages,
                "peers": peers,
            }

    async def join(self, send: Any) -> Peer:
        peer_id = secrets.token_hex(4)
        async with self._lock:
            self.total_connections += 1
            peer = Peer(
                id=peer_id,
                name=f"peer-{peer_id}",
                connected_at_ms=_now_ms(),
                send=send,
            )
            self._peers[peer_id] = peer
        await self.emit(peer, "system", {"message": "connected", "peer": self._public_peer(peer)})
        await self.broadcast("presence", {"action": "join", "peer": self._public_peer(peer)}, skip=peer.id)
        return peer

    async def leave(self, peer: Peer) -> None:
        async with self._lock:
            self._peers.pop(peer.id, None)
        await self.broadcast("presence", {"action": "leave", "peer": self._public_peer(peer)})

    async def emit(self, peer: Peer, event: str, payload: dict[str, Any]) -> None:
        await peer.send({"type": "websocket.send", "text": json.dumps({"event": event, "ts": _now_ms(), **payload})})

    async def broadcast(self, event: str, payload: dict[str, Any], *, skip: str | None = None) -> None:
        async with self._lock:
            peers = [peer for peer in self._peers.values() if peer.id != skip]
        for peer in peers:
            try:
                await self.emit(peer, event, payload)
            except Exception:
                pass

    async def record_text(self, peer: Peer, text: str) -> None:
        async with self._lock:
            peer.message_count += 1
            peer.bytes_received += len(text.encode("utf-8"))
            peer.last_seen_ms = _now_ms()
            self.total_messages += 1

    async def record_bytes(self, peer: Peer, data: bytes) -> None:
        async with self._lock:
            peer.message_count += 1
            peer.bytes_received += len(data)
            peer.last_seen_ms = _now_ms()
            self.total_messages += 1

    async def rename(self, peer: Peer, name: str) -> None:
        clean = name.strip()[:40] or peer.name
        async with self._lock:
            peer.name = clean
            peer.last_seen_ms = _now_ms()
        await self.broadcast("presence", {"action": "rename", "peer": self._public_peer(peer)})

    def _public_peer(self, peer: Peer) -> dict[str, Any]:
        return {"id": peer.id, "name": peer.name, "connected_at_ms": peer.connected_at_ms}


hub = WebSocketHub()


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    scope_type = scope["type"]
    if scope_type == "lifespan":
        await _lifespan(receive, send)
        return
    if scope_type == "http":
        await _http(scope, receive, send)
        return
    if scope_type == "websocket":
        await _websocket(scope, receive, send)
        return
    raise RuntimeError(f"Unsupported ASGI scope: {scope_type}")


async def _lifespan(receive: Any, send: Any) -> None:
    while True:
        event = await receive()
        if event["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif event["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _http(scope: dict[str, Any], receive: Any, send: Any) -> None:
    while True:
        event = await receive()
        if event["type"] == "http.request" and not event.get("more_body", False):
            break
    path = scope.get("path", "/")
    if path == "/health":
        await _send_json(send, 200, {"ok": True, "service": "tigrcorn-websocket-uix-demo"})
    elif path == "/state":
        await _send_json(send, 200, await hub.snapshot())
    else:
        await _send_json(send, 404, {"ok": False, "error": "not_found", "paths": ["/health", "/state", "/ws"]})


async def _websocket(scope: dict[str, Any], receive: Any, send: Any) -> None:
    if scope.get("path") != "/ws":
        await send({"type": "websocket.close", "code": 1008, "reason": "Use /ws"})
        return
    connect = await receive()
    if connect["type"] != "websocket.connect":
        return
    await send({"type": "websocket.accept", "headers": [(b"x-tigrcorn-demo", b"websocket-uix")]})
    peer = await hub.join(send)
    try:
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            if event.get("text") is not None:
                await hub.record_text(peer, event["text"])
                await _handle_text(peer, event["text"])
            elif event.get("bytes") is not None:
                await hub.record_bytes(peer, event["bytes"])
                await _handle_bytes(peer, event["bytes"])
    finally:
        await hub.leave(peer)


async def _handle_text(peer: Peer, text: str) -> None:
    try:
        message = json.loads(text)
    except json.JSONDecodeError:
        await hub.emit(peer, "echo", {"mode": "text", "text": text})
        return

    action = message.get("action", "echo")
    if action == "ping":
        await hub.emit(peer, "pong", {"client_ts": message.get("ts"), "state": await hub.snapshot()})
    elif action == "rename":
        await hub.rename(peer, str(message.get("name", "")))
    elif action == "broadcast":
        text_body = str(message.get("text", ""))
        await hub.broadcast("message", {"from": hub._public_peer(peer), "text": text_body})
    elif action == "echo":
        await hub.emit(peer, "echo", {"mode": "json", "data": message})
    else:
        await hub.emit(peer, "error", {"message": f"unknown action: {action}"})


async def _handle_bytes(peer: Peer, data: bytes) -> None:
    await hub.emit(
        peer,
        "echo",
        {
            "mode": "bytes",
            "size": len(data),
            "base64": base64.b64encode(data[:256]).decode("ascii"),
            "truncated": len(data) > 256,
        },
    )

