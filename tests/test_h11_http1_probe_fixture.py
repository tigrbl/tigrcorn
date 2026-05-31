from __future__ import annotations

import asyncio
import unittest

from tests.fixtures_third_party.h11_http1_client import probe_http11
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


async def _start_http11_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["1.1"])
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


class H11HTTP1ProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_h11_probe_drives_tigrcorn_http11_roundtrip(self):
        observed: list[dict] = []

        async def app(scope, receive, send):
            event = await receive()
            observed.append(scope)
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"h11:" + event["body"], "more_body": False})

        server, port = await _start_http11_server(app)
        try:
            response = await probe_http11(
                "127.0.0.1",
                port,
                method="POST",
                target="/h11-probe",
                headers=[("x-probe", "h11")],
                body=b"hello",
            )
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"h11:hello")
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")
        self.assertEqual(observed[0]["type"], "http")
        self.assertEqual(observed[0]["path"], "/h11-probe")
        self.assertIn((b"x-probe", b"h11"), observed[0]["headers"])


if __name__ == "__main__":
    unittest.main()
