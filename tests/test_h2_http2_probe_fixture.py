from __future__ import annotations

import unittest

from tests.fixtures_third_party.h2_http2_client import probe_h2c
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


async def _start_h2_server(app):
    config = build_config(host="127.0.0.1", port=0, lifespan="off", http_versions=["2"], enable_h2c=True)
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


class H2HTTP2ProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_h2_probe_drives_tigrcorn_http2_roundtrip(self):
        observed: list[dict] = []

        async def app(scope, receive, send):
            event = await receive()
            observed.append(scope)
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"h2:" + event["body"], "more_body": False})

        server, port = await _start_h2_server(app)
        try:
            response = await probe_h2c(
                "127.0.0.1",
                port,
                method="POST",
                path="/h2-probe",
                headers=[("x-probe", "h2")],
                body=b"hello",
            )
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"h2:hello")
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")
        self.assertTrue(response.stream_ended)
        self.assertEqual(observed[0]["type"], "http")
        self.assertEqual(observed[0]["http_version"], "2")
        self.assertEqual(observed[0]["path"], "/h2-probe")
        self.assertIn((b"x-probe", b"h2"), observed[0]["headers"])


if __name__ == "__main__":
    unittest.main()
