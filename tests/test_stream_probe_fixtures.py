from __future__ import annotations

import asyncio
import unittest

from tests.fixtures_third_party.h11_stream_client import probe_h11_stream
from tests.fixtures_third_party.h2_stream_client import probe_h2_stream
from tests.fixtures_third_party.h3_stream_client import probe_h3_stream
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


STREAM_BODY = b"alpha-beta-gamma"
STREAM_CHUNKS = (b"alpha-", b"beta-", b"gamma")


async def _streaming_app(scope, receive, send):
    await receive()
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    for index, chunk in enumerate(STREAM_CHUNKS):
        await send({"type": "http.response.body", "body": chunk, "more_body": index < len(STREAM_CHUNKS) - 1})
        await asyncio.sleep(0)


async def _start_server(app, *, http_versions: list[str], transport: str = "tcp"):
    kwargs = {"host": "127.0.0.1", "port": 0, "lifespan": "off", "http_versions": http_versions}
    if transport == "tcp" and "2" in http_versions:
        kwargs["enable_h2c"] = True
    if transport == "udp":
        kwargs.update({"transport": "udp", "protocols": ["http3"], "quic_secret": b"shared"})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info("sockname")[1] if transport == "udp" else listener.server.sockets[0].getsockname()[1]
    return server, port


class StreamProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_h11_stream_probe_observes_streamed_response_body(self):
        server, port = await _start_server(_streaming_app, http_versions=["1.1"])
        try:
            response = await probe_h11_stream("127.0.0.1", port, target="/stream")
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, STREAM_BODY)
        self.assertTrue(response.complete)
        self.assertGreaterEqual(response.data_event_count, 1)
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")

    async def test_h2_stream_probe_observes_streamed_response_body(self):
        server, port = await _start_server(_streaming_app, http_versions=["2"])
        try:
            response = await probe_h2_stream("127.0.0.1", port, path="/stream")
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, STREAM_BODY)
        self.assertTrue(response.ended)
        self.assertGreaterEqual(response.data_event_count, 1)
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")

    async def test_h3_stream_probe_observes_streamed_response_body(self):
        server, port = await _start_server(_streaming_app, http_versions=["3"], transport="udp")
        try:
            response = await probe_h3_stream("127.0.0.1", port, path="/stream")
        finally:
            await server.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, STREAM_BODY)
        self.assertTrue(response.ended)
        self.assertGreaterEqual(response.stream_event_count, 1)
        self.assertIn("stream", response.quic_events)
        self.assertEqual(response.header_map()[b"content-type"], b"text/plain")


if __name__ == "__main__":
    unittest.main()
