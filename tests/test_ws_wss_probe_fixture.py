from __future__ import annotations

import unittest
from pathlib import Path

from tests.fixtures_third_party.ws_wss_client import probe_ws_wss
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


ROOT = Path(__file__).resolve().parent
CERTS = ROOT / "fixtures_certs"
SERVER_CERT = CERTS / "interop-localhost-cert.pem"
SERVER_KEY = CERTS / "interop-localhost-key.pem"


async def _start_websocket_server(app, *, tls: bool = False):
    kwargs = {
        "host": "127.0.0.1",
        "port": 0,
        "lifespan": "off",
        "http_versions": ["1.1"],
        "websocket": True,
    }
    if tls:
        kwargs.update({"ssl_certfile": str(SERVER_CERT), "ssl_keyfile": str(SERVER_KEY)})
    config = build_config(**kwargs)
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.server.sockets[0].getsockname()[1]
    return server, port


async def _echo_websocket_app(scope, receive, send):
    assert scope["type"] == "websocket"
    connect = await receive()
    assert connect["type"] == "websocket.connect"
    await send({"type": "websocket.accept", "headers": []})
    message = await receive()
    await send({"type": "websocket.send", "text": message["text"]})
    await send({"type": "websocket.close", "code": 1000})


class WsWssProbeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_ws_probe_drives_plain_websocket_roundtrip(self):
        server, port = await _start_websocket_server(_echo_websocket_app)
        try:
            response = await probe_ws_wss("127.0.0.1", port, path="/ws", text="hello-ws")
        finally:
            await server.close()

        self.assertFalse(response.secure)
        self.assertEqual(response.received_text, "hello-ws")
        self.assertEqual(response.close_code, 1000)
        self.assertIsNone(response.tls_cipher)

    async def test_wss_probe_drives_tls_websocket_roundtrip(self):
        server, port = await _start_websocket_server(_echo_websocket_app, tls=True)
        try:
            response = await probe_ws_wss(
                "localhost",
                port,
                path="/ws",
                text="hello-wss",
                secure=True,
                cafile=str(SERVER_CERT),
                server_hostname="localhost",
            )
        finally:
            await server.close()

        self.assertTrue(response.secure)
        self.assertEqual(response.received_text, "hello-wss")
        self.assertEqual(response.close_code, 1000)
        self.assertIsNotNone(response.tls_cipher)
        self.assertEqual(response.selected_alpn_protocol, "http/1.1")


if __name__ == "__main__":
    unittest.main()
