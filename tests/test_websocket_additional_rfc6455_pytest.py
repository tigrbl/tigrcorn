import asyncio
import base64
import os

from tigrcorn.config.load import build_config
from tigrcorn.protocols.websocket.frames import (
import pytest
    decode_close_payload,
    encode_frame,
    read_frame,
)
from tigrcorn.protocols.websocket.handler import _WSAppSend
from tigrcorn.server.runner import TigrCornServer


async def _start_server(app, *, websocket_max_message_size: int | None = None):
    config = build_config(
        host="127.0.0.1", port=0, lifespan="off", http_versions=["1.1"]
    )
    if websocket_max_message_size is not None:
        config.websocket_max_message_size = websocket_max_message_size
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


async def _open_websocket(port: int):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    key = base64.b64encode(os.urandom(16))
    request = (
        b"GET /ws HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"Sec-WebSocket-Key: " + key + b"\r\n\r\n"
    )
    writer.write(request)
    await writer.drain()
    response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1.0)
    return reader, writer, response


class TestWebSocketAdditionalRFC6455Tests:
    async def test_accept_rejects_extension_negotiation(self):
        sender = _WSAppSend(
            writer=type(
                "W",
                (),
                {
                    "write": lambda self, data: None,
                    "drain": staticmethod(asyncio.sleep),
                },
            )(),
            server_header=None,
            state={
                "accepted": False,
                "closed": False,
                "http_denied": False,
                "http_denial_status": 403,
                "http_denial_headers": [],
                "http_denial_started": False,
                "sec_websocket_key": b"dGhlIHNhbXBsZSBub25jZQ==",
            },
            accepted=asyncio.Event(),
            allowed_subprotocols=[],
        )
        with pytest.raises(RuntimeError):
            await sender(
                {
                    "type": "websocket.accept",
                    "headers": [(b"sec-websocket-extensions", b"permessage-deflate")],
                }
            )

    async def test_invalid_utf8_text_message_closes_with_1007(self):
        disconnects: list[dict] = []

        async def app(scope, receive, send):
            await receive()
            await send({"type": "websocket.accept", "headers": []})
            disconnects.append(await receive())

        server, port = await _start_server(app)
        try:
            reader, writer, response = await _open_websocket(port)
            assert b"101 Switching Protocols" in response
            writer.write(encode_frame(opcode=1, payload=b"\xff", fin=True, masked=True))
            await writer.drain()
            frame = await asyncio.wait_for(
                read_frame(reader, max_payload_size=1024, expect_masked=False), 1.0
            )
            code, reason = decode_close_payload(frame.payload)
            assert code == 1007
            assert reason == "invalid frame payload data"
            assert disconnects[0]["code"] == 1007
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_fragmented_message_limit_closes_with_1009(self):
        disconnects: list[dict] = []

        async def app(scope, receive, send):
            await receive()
            await send({"type": "websocket.accept", "headers": []})
            disconnects.append(await receive())

        server, port = await _start_server(app, websocket_max_message_size=4)
        try:
            reader, writer, response = await _open_websocket(port)
            assert b"101 Switching Protocols" in response
            writer.write(encode_frame(opcode=1, payload=b"abc", fin=False, masked=True))
            writer.write(encode_frame(opcode=0, payload=b"de", fin=True, masked=True))
            await writer.drain()
            frame = await asyncio.wait_for(
                read_frame(reader, max_payload_size=1024, expect_masked=False), 1.0
            )
            code, _reason = decode_close_payload(frame.payload)
            assert code == 1009
            assert disconnects[0]["code"] == 1009
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
