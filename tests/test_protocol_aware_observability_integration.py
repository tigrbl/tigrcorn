from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import ssl
from pathlib import Path

from tigrcorn.config.load import build_config
from tigrcorn.protocols.websocket.frames import encode_frame, read_frame
from tigrcorn.server.runner import TigrCornServer


CERTS = Path(__file__).resolve().parent / "fixtures_certs"
SERVER_CERT = CERTS / "interop-localhost-cert.pem"
SERVER_KEY = CERTS / "interop-localhost-key.pem"


async def _app(scope, receive, send) -> None:
    if scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.accept", "headers": []})
        await receive()
        await send({"type": "websocket.close", "code": 1000})
        return
    await receive()
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _start_server(*, tls: bool = False, websocket: bool = False) -> tuple[TigrCornServer, int]:
    config = build_config(
        host="127.0.0.1",
        port=0,
        lifespan="off",
        http_versions=["1.1"],
        websocket=websocket,
        ssl_certfile=str(SERVER_CERT) if tls else None,
        ssl_keyfile=str(SERVER_KEY) if tls else None,
    )
    server = TigrCornServer(_app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


async def _http_request(port: int, request: bytes, *, tls: bool = False) -> bytes:
    ssl_context = None
    server_hostname = None
    if tls:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(SERVER_CERT))
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
        ssl_context.set_alpn_protocols(["http/1.1"])
        server_hostname = "localhost"
    reader, writer = await asyncio.open_connection(
        "127.0.0.1",
        port,
        ssl=ssl_context,
        server_hostname=server_hostname,
    )
    writer.write(request)
    await writer.drain()
    response = await reader.read(65535)
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()
    return response


def _last_record(server: TigrCornServer) -> dict:
    assert server.access_logger.observability_records
    return server.access_logger.observability_records[-1]


def test_http_request_emits_protocol_transport_labels() -> None:
    async def run() -> dict:
        server, port = await _start_server()
        try:
            response = await _http_request(port, b"GET /hello HTTP/1.1\r\nHost: localhost\r\n\r\n")
            assert b"204 No Content" in response
            return _last_record(server)
        finally:
            await server.close()

    record = asyncio.run(run())

    assert record["name"] == "http.request"
    assert record["labels"]["protocol"] == "http1"
    assert record["labels"]["transport"] == "tcp"


def test_tls_request_emits_tls_alpn_labels() -> None:
    async def run() -> dict:
        server, port = await _start_server(tls=True)
        try:
            response = await _http_request(port, b"GET /tls HTTP/1.1\r\nHost: localhost\r\n\r\n", tls=True)
            assert b"204 No Content" in response
            return _last_record(server)
        finally:
            await server.close()

    record = asyncio.run(run())

    assert record["labels"]["tls_version"] == "TLSv1.3"
    assert record["labels"]["alpn"] == "http/1.1"
    assert record["labels"]["protocol"] == "http1"


def test_websocket_lifecycle_emits_observability_event() -> None:
    async def run() -> dict:
        server, port = await _start_server(websocket=True)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            key = base64.b64encode(os.urandom(16))
            writer.write(
                b"GET /ws HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Version: 13\r\n"
                b"Sec-WebSocket-Key: " + key + b"\r\n\r\n"
            )
            await writer.drain()
            response = await reader.readuntil(b"\r\n\r\n")
            assert b"101 Switching Protocols" in response
            writer.write(encode_frame(opcode=1, payload=b"hello", fin=True, masked=True))
            await writer.drain()
            await read_frame(reader, max_payload_size=1024, expect_masked=False)
            for _ in range(20):
                if server.access_logger.observability_records:
                    break
                await asyncio.sleep(0.01)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return _last_record(server)
        finally:
            await server.close()

    record = asyncio.run(run())

    assert record["name"] == "websocket.accepted"
    assert record["labels"]["protocol"] == "websocket"
    assert record["labels"]["transport"] == "tcp"
    assert record["labels"]["lifecycle"] == "accepted"


def test_observability_runtime_redacts_authorization_header() -> None:
    async def run() -> dict:
        server, port = await _start_server()
        try:
            await _http_request(
                port,
                b"GET /secret HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Authorization: Bearer runtime-secret-token\r\n\r\n",
            )
            return _last_record(server)
        finally:
            await server.close()

    record = asyncio.run(run())
    rendered = str(record)

    assert record["attributes"]["headers"]["authorization"] == "[redacted]"
    assert "runtime-secret-token" not in rendered


def test_observability_peer_cardinality_is_hashed_in_access_event() -> None:
    async def run() -> dict:
        server, port = await _start_server()
        try:
            await _http_request(port, b"GET /accounts/123456/private HTTP/1.1\r\nHost: localhost\r\n\r\n")
            return _last_record(server)
        finally:
            await server.close()

    record = asyncio.run(run())
    rendered = str(record)

    assert record["labels"]["peer_hash"]
    assert record["labels"]["path_hash"]
    assert "127.0.0.1:" not in rendered
    assert "/accounts/123456/private" not in rendered
