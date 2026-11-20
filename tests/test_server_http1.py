import asyncio
import unittest

from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


async def _start_server(app, *, max_body_size=None):
    config = build_config(
        host="127.0.0.1", port=0, lifespan="off", http_versions=["1.1"],
        max_body_size=max_body_size,
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


class HTTP1ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_http11_oversized_body_returns_413(self):
        received = []

        async def app(scope, receive, send):
            while True:
                event = await receive()
                received.append(event["body"])
                if not event["more_body"]:
                    break
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body"})

        server, port = await _start_server(app, max_body_size=5)
        try:
            for payload, status in (
                (b"Content-Length: 6\r\nExpect: 100-continue\r\n\r\n", b"413"),
                (b"Transfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n3\r\n", b"413"),
                (b"Content-Length: 5\r\n\r\nabcde", b"204"),
            ):
                with self.subTest(status=status, payload=payload):
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    try:
                        writer.write(b"POST / HTTP/1.1\r\nHost: localhost\r\n" + payload)
                        await writer.drain()
                        headers = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
                        self.assertEqual(headers.split(b" ", 2)[1], status)
                        if status == b"413":
                            self.assertIn(b"connection: close", headers.lower())
                    finally:
                        writer.close()
                        await writer.wait_closed()
            self.assertEqual(received, [b"abc", b"abcde"])
        finally:
            await server.close()

    async def test_http11_roundtrip(self):
        async def app(scope, receive, send):
            event = await receive()
            self.assertEqual(scope["type"], "http")
            self.assertEqual(scope["path"], "/echo")
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": event["body"], "more_body": False})

        server, port = await _start_server(app)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"POST /echo HTTP/1.1\r\nHost: localhost\r\nContent-Length: 5\r\n\r\nhello")
            await writer.drain()
            data = await reader.read(65535)
            self.assertIn(b"200 OK", data)
            self.assertTrue(data.endswith(b"hello"))
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()


if __name__ == "__main__":
    unittest.main()
