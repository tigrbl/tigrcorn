from __future__ import annotations

import unittest

from tests.fixtures_third_party.h3_quic_client import probe_h3_quic
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


async def _start_h3_quic_server(app):
    config = build_config(
        transport="udp",
        host="127.0.0.1",
        port=0,
        lifespan="off",
        http_versions=["3"],
        protocols=["http3"],
        quic_secret=b"shared",
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info("sockname")[1]
    return server, port


class H3QuicProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_h3_quic_probe_reports_http3_response_and_quic_carrier_events(self):
        observed: list[dict] = []

        async def app(scope, receive, send):
            event = await receive()
            observed.append(scope)
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"h3-quic:" + event["body"], "more_body": False})

        server, port = await _start_h3_quic_server(app)
        try:
            response = await probe_h3_quic(
                "127.0.0.1",
                port,
                method="POST",
                path="/h3-quic-probe",
                headers=[("x-probe", "h3-quic")],
                body=b"hello",
            )
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"h3-quic:hello")
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")
        self.assertTrue(response.ended)
        self.assertGreaterEqual(response.datagrams_sent, 2)
        self.assertGreaterEqual(response.datagrams_received, 2)
        self.assertGreater(response.bytes_sent, 0)
        self.assertGreater(response.bytes_received, 0)
        self.assertIn("ack", response.quic_events)
        self.assertIn("stream", response.quic_events)
        self.assertEqual(observed[0]["type"], "http")
        self.assertEqual(observed[0]["http_version"], "3")
        self.assertEqual(observed[0]["path"], "/h3-quic-probe")
        self.assertIn((b"x-probe", b"h3-quic"), observed[0]["headers"])


if __name__ == "__main__":
    unittest.main()
