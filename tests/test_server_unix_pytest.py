import asyncio
import os
import tempfile

from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


import pytest

async def test_unix_http_roundtrip():
    async def app(scope, receive, send):
        event = await receive()
        assert scope["type"] == "http"
        assert scope["path"] == "/unix"
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"ok:" + event["body"],
                "more_body": False,
            }
        )

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tigrcorn.sock")
        config = build_config(uds=path, lifespan="off", http_versions=["1.1"])
        server = TigrCornServer(app, config)
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(path)
            writer.write(
                b"POST /unix HTTP/1.1\r\nHost: localhost\r\nContent-Length: 3\r\n\r\nhey"
            )
            await writer.drain()
            data = await reader.read(65535)
            assert b"200 OK" in data
            assert data.endswith(b"ok:hey")
            writer.close()
            await writer.wait_closed()
        finally:
            await server.close()
