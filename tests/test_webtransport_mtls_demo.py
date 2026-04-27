from __future__ import annotations

import asyncio
import os
import socket
import tempfile
import unittest
from pathlib import Path

from examples.webtransport_mtls_demo.server import app
from tigrcorn.config.load import build_config
from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import (
    FRAME_SETTINGS,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_H3_DATAGRAM,
    STREAM_TYPE_CONTROL,
    encode_frame,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.utils.bytes import encode_quic_varint


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "examples" / "webtransport_mtls_demo" / "docker-compose.yml"
CLIENT_HTML = ROOT / "examples" / "webtransport_mtls_demo" / "client" / "index.html"


class WebTransportMtlsDemoConfigTests(unittest.TestCase):
    def test_compose_exposes_local_and_strict_mtls_webtransport_endpoints(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("tigrcorn-wt-local:", compose)
        self.assertIn("--port 8444", compose)
        self.assertIn('"8444:8444/udp"', compose)
        self.assertIn("tigrcorn-wt-mtls:", compose)
        self.assertIn("--port 8443", compose)
        self.assertIn('"8443:8443/udp"', compose)
        self.assertIn("--protocol", compose)
        self.assertIn("webtransport", compose)
        self.assertIn("--http", compose)
        self.assertIn("--ssl-certfile /certs/server-cert.pem", compose)
        self.assertIn("--ssl-keyfile /certs/server-key.pem", compose)
        self.assertIn("--ssl-ca-certs", compose)
        self.assertIn("--ssl-require-client-cert", compose)
        self.assertIn('TIGRCORN_DEMO_REQUIRE_MTLS: "true"', compose)
        self.assertIn("wt-certs:", compose)
        self.assertIn("cert_setup", compose)

    def test_browser_ui_defaults_to_local_handshake_endpoint(self) -> None:
        html = CLIENT_HTML.read_text(encoding="utf-8")

        self.assertIn('value="https://localhost:8444/wt"', html)
        self.assertIn('data-endpoint="https://localhost:8444/wt"', html)
        self.assertIn('data-endpoint="https://localhost:8443/wt"', html)
        client_js = (CLIENT_HTML.parent / "main.js").read_text(encoding="utf-8")
        self.assertIn("serverCertificateHashes", client_js)
        self.assertIn('/cert-hash.json', client_js)


class WebTransportMtlsDemoAppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        os.environ.pop("TIGRCORN_DEMO_REQUIRE_MTLS", None)

    async def test_local_mode_accepts_non_mtls_security_metadata(self) -> None:
        os.environ.pop("TIGRCORN_DEMO_REQUIRE_MTLS", None)
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return {"type": "webtransport.close", "session_id": "s1"}

        async def send(event: dict[str, object]) -> None:
            sent.append(event)

        await app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )

        self.assertEqual(sent[0]["type"], "webtransport.accept")

    async def test_strict_mode_closes_non_mtls_security_metadata(self) -> None:
        os.environ["TIGRCORN_DEMO_REQUIRE_MTLS"] = "true"
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return {"type": "webtransport.close", "session_id": "s1"}

        async def send(event: dict[str, object]) -> None:
            sent.append(event)

        await app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.security": {"tls": True, "mtls": False}, "tigrcorn.unit": {"session_id": "s1"}},
            },
            receive,
            send,
        )

        self.assertEqual(sent, [{"type": "webtransport.close", "session_id": "s1", "code": 403, "reason": "mTLS required"}])

    async def test_local_webtransport_listener_completes_quic_tls_handshake(self) -> None:
        cert_pem, key_pem = generate_self_signed_certificate("server.example")
        with tempfile.TemporaryDirectory() as tmpdir:
            certfile = Path(tmpdir) / "server-cert.pem"
            keyfile = Path(tmpdir) / "server-key.pem"
            certfile.write_bytes(cert_pem)
            keyfile.write_bytes(key_pem)

            config = build_config(
                transport="udp",
                host="127.0.0.1",
                port=0,
                lifespan="off",
                http_versions=["3"],
                protocols=["webtransport"],
                ssl_certfile=str(certfile),
                ssl_keyfile=str(keyfile),
                webtransport_path="/wt",
                webtransport_origins=["https://localhost:8088"],
            )
            server = TigrCornServer(app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtlocal1")
            client.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name="server.example",
                    trusted_certificates=[cert_pem],
                )
            )
            loop = asyncio.get_running_loop()
            try:
                sock.sendto(client.start_handshake(), ("127.0.0.1", port))
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    client.receive_datagram(data)
                    for datagram in client.take_handshake_datagrams():
                        sock.sendto(datagram, ("127.0.0.1", port))
                    if client.handshake_driver is not None and client.handshake_driver.complete:
                        break

                self.assertIsNotNone(client.handshake_driver)
                assert client.handshake_driver is not None
                self.assertTrue(client.handshake_driver.complete)
            finally:
                sock.close()
                await server.close()

    async def test_local_webtransport_listener_accepts_extended_connect(self) -> None:
        cert_pem, key_pem = generate_self_signed_certificate("server.example")
        with tempfile.TemporaryDirectory() as tmpdir:
            certfile = Path(tmpdir) / "server-cert.pem"
            keyfile = Path(tmpdir) / "server-key.pem"
            certfile.write_bytes(cert_pem)
            keyfile.write_bytes(key_pem)

            config = build_config(
                transport="udp",
                host="127.0.0.1",
                port=0,
                lifespan="off",
                http_versions=["3"],
                protocols=["webtransport"],
                ssl_certfile=str(certfile),
                ssl_keyfile=str(keyfile),
                webtransport_path="/wt",
                webtransport_origins=["https://localhost:8088"],
            )
            server = TigrCornServer(app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtconn01")
            client.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name="server.example",
                    trusted_certificates=[cert_pem],
                )
            )
            core = HTTP3ConnectionCore()
            loop = asyncio.get_running_loop()
            loop_errors: list[BaseException] = []
            previous_exception_handler = loop.get_exception_handler()

            def capture_loop_exception(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
                exception = context.get("exception")
                if isinstance(exception, BaseException):
                    loop_errors.append(exception)

            loop.set_exception_handler(capture_loop_exception)
            try:
                sock.sendto(client.start_handshake(), ("127.0.0.1", port))
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                    for datagram in client.take_handshake_datagrams():
                        sock.sendto(datagram, ("127.0.0.1", port))
                    if client.handshake_driver is not None and client.handshake_driver.complete:
                        break

                control_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
                control_payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(FRAME_SETTINGS, b"")
                sock.sendto(client.send_stream_data(control_stream_id, control_payload, fin=False), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ]
                )
                sock.sendto(client.send_stream_data(0, payload, fin=False), ("127.0.0.1", port))

                response_state = None
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None:
                                response_state = candidate
                    if response_state is not None and response_state.received_initial_headers:
                        break

                self.assertIn(SETTING_ENABLE_CONNECT_PROTOCOL, core.state.remote_settings)
                self.assertEqual(core.state.remote_settings.get(SETTING_H3_DATAGRAM), 1)
                self.assertEqual(core.state.remote_settings.get(SETTING_ENABLE_WEBTRANSPORT), 1)
                self.assertIsNotNone(response_state)
                assert response_state is not None
                self.assertIn((b":status", b"200"), response_state.headers)
                self.assertIn((b"sec-webtransport-http3-draft", b"draft02"), response_state.headers)
                self.assertEqual(loop_errors, [])
            finally:
                loop.set_exception_handler(previous_exception_handler)
                sock.close()
                await server.close()
