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
    encode_settings,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint


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
