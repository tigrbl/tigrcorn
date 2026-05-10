import asyncio
import base64
import os
import socket
import unittest

from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.websocket.frames import encode_frame, parse_frame_bytes, read_frame
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(app, *, http_versions: list[str], transport: str = "tcp"):
    kwargs = {
        "host": "127.0.0.1",
        "port": 0,
        "lifespan": "off",
        "http_versions": http_versions,
    }
    if transport == "udp":
        kwargs.update(
            {
                "transport": "udp",
                "protocols": ["http3"],
                "quic_secret": b"shared",
            }
        )
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    if transport == "udp":
        port = listener.transport.get_extra_info("sockname")[1]
    else:
        port = listener.server.sockets[0].getsockname()[1]
    return server, port


def _frame_wire_length(data: bytes) -> int:
    if len(data) < 2:
        raise AssertionError("websocket frame is truncated")
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    pos = 2
    if length == 126:
        if len(data) < pos + 2:
            raise AssertionError("websocket frame is truncated")
        length = int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise AssertionError("websocket frame is truncated")
        length = int.from_bytes(data[pos:pos + 8], "big")
        pos += 8
    if masked:
        pos += 4
    total = pos + length
    if len(data) < total:
        raise AssertionError("websocket frame is truncated")
    return total


class WebSocketRFC8307Tests(unittest.IsolatedAsyncioTestCase):
    def test_scope_preserves_well_known_path(self):
        request = ParsedRequest(
            method="GET",
            target="/.well-known/websocket",
            path="/.well-known/websocket",
            raw_path=b"/.well-known/websocket",
            query_string=b"",
            http_version="1.1",
            headers=[],
            body=b"",
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=True,
        )

        scope = build_websocket_scope(
            request,
            client=("127.0.0.1", 50000),
            server=("127.0.0.1", 8000),
            scheme="ws",
        )

        self.assertEqual(scope["scheme"], "ws")
        self.assertEqual(scope["path"], "/.well-known/websocket")
        self.assertEqual(scope["raw_path"], b"/.well-known/websocket")

    async def test_http11_websocket_roundtrip_on_well_known_path(self):
        seen = {}

        async def app(scope, receive, send):
            seen["path"] = scope["path"]
            seen["scheme"] = scope["scheme"]
            await receive()
            await send({"type": "websocket.accept", "headers": []})
            event = await receive()
            await send({"type": "websocket.send", "text": event["text"]})
            await send({"type": "websocket.close", "code": 1000})

        server, port = await _start_server(app, http_versions=["1.1"])
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            key = base64.b64encode(os.urandom(16))
            request = (
                b"GET /.well-known/websocket HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Version: 13\r\n"
                b"Sec-WebSocket-Key: " + key + b"\r\n\r\n"
            )
            writer.write(request)
            await writer.drain()
            response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1.0)
            self.assertIn(b"101 Switching Protocols", response)
            writer.write(encode_frame(0x1, b"well-known", masked=True))
            await writer.drain()
            frame = await asyncio.wait_for(read_frame(reader, max_payload_size=1024, expect_masked=False), 1.0)
            self.assertEqual(frame.payload.decode("utf-8"), "well-known")
            self.assertEqual(seen, {"path": "/.well-known/websocket", "scheme": "ws"})
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()

    async def test_http3_websocket_roundtrip_on_well_known_path(self):
        seen = {}

        async def app(scope, receive, send):
            seen["path"] = scope["path"]
            seen["scheme"] = scope["scheme"]
            await receive()
            await send({"type": "websocket.accept", "headers": []})
            event = await receive()
            await send({"type": "websocket.send", "text": event["text"]})
            await send({"type": "websocket.close", "code": 1000})

        server, port = await _start_server(app, http_versions=["3"], transport="udp")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b"shared", local_cid=b"cli3")
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ("127.0.0.1", port))
            for _ in range(4):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == "stream":
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                    break

            payload = core.get_request(0).encode_request(
                [
                    (b":method", b"CONNECT"),
                    (b":protocol", b"websocket"),
                    (b":scheme", b"https"),
                    (b":path", b"/.well-known/websocket"),
                    (b":authority", b"example"),
                    (b"sec-websocket-version", b"13"),
                ],
                encode_frame(0x1, b"well-known-h3", masked=True),
            )
            sock.sendto(client.send_stream_data(0, payload, fin=False), ("127.0.0.1", port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == "stream":
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None and response_state.ended:
                    break

            self.assertIsNotNone(response_state)
            assert response_state is not None
            self.assertIn((b":status", b"200"), response_state.headers)
            first_len = _frame_wire_length(response_state.body)
            message_frame = parse_frame_bytes(response_state.body[:first_len], expect_masked=False)
            self.assertEqual(message_frame.payload.decode("utf-8"), "well-known-h3")
            self.assertEqual(seen, {"path": "/.well-known/websocket", "scheme": "wss"})
        finally:
            sock.close()
            await server.close()
