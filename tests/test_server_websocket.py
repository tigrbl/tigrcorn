import asyncio
import base64
import os
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.protocols.websocket.frames import encode_frame, read_frame
from tigrcorn.server.runner import TigrCornServer


async def _start_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["1.1"])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


class WebSocketServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_echo(self):
        async def app(scope, receive, send):
            self.assertEqual(scope["type"], "websocket")
            connect = await receive()
            self.assertEqual(connect["type"], "websocket.connect")
            await send({"type": "websocket.accept", "headers": []})
            message = await receive()
            await send({"type": "websocket.send", "text": message.get("text")})
            await send({"type": "websocket.close", "code": 1000})

        server, port = await _start_server(app)
        try:
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
            response = await reader.readuntil(b"\r\n\r\n")
            self.assertIn(b"101 Switching Protocols", response)
            writer.write(encode_frame(opcode=1, payload=b"hello", fin=True, masked=True))
            await writer.drain()
            frame = await read_frame(reader, max_payload_size=1024, expect_masked=False)
            self.assertEqual(frame.payload, b"hello")
            close_frame = await read_frame(reader, max_payload_size=1024, expect_masked=False)
            self.assertEqual(close_frame.opcode, 8)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


if __name__ == "__main__":
    unittest.main()
