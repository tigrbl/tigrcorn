from __future__ import annotations

import unittest
from pathlib import Path

from examples.h3_asgi3_lab.app import app


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "h3_asgi3_lab"


class H3Asgi3LabConfigTests(unittest.TestCase):
    def test_compose_runs_tigrcorn_h3_asgi3_and_uix_containers(self) -> None:
        compose = (EXAMPLE / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("tigrcorn-h3-asgi3:", compose)
        self.assertIn("tigrcorn examples.h3_asgi3_lab.app:app", compose)
        self.assertIn("--app-interface asgi3", compose)
        self.assertIn("--transport udp", compose)
        self.assertIn("--protocol http3", compose)
        self.assertIn("--http 3", compose)
        self.assertNotIn("webtransport", compose.lower())
        self.assertIn('"8445:8445/udp"', compose)
        self.assertIn("tigrcorn-h3-uix:", compose)
        self.assertIn("examples.h3_asgi3_lab.uix_server", compose)
        self.assertIn('"8091:8090/tcp"', compose)

    def test_uix_uses_h3_probe_endpoint_without_webtransport_api(self) -> None:
        html = (EXAMPLE / "uix" / "index.html").read_text(encoding="utf-8")
        js = (EXAMPLE / "uix" / "main.js").read_text(encoding="utf-8")

        self.assertIn('value="/inspect?payload=hello-over-h3"', html)
        self.assertIn("/h3-probe", js)
        self.assertIn("h3/quic", js)
        self.assertNotIn("WebTransport", js)
        self.assertNotIn("serverCertificateHashes", js)


class H3Asgi3LabAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_http3_asgi_scope_returns_probe_payload(self) -> None:
        sent: list[dict[str, object]] = []
        received = False

        async def receive() -> dict[str, object]:
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(event: dict[str, object]) -> None:
            sent.append(event)

        await app(
            {
                "type": "http",
                "http_version": "3",
                "method": "GET",
                "path": "/inspect",
                "query_string": b"payload=hello",
                "scheme": "https",
                "extensions": {"tigrcorn.transport": {"protocol": "quic"}},
            },
            receive,
            send,
        )

        self.assertEqual(sent[0]["type"], "http.response.start")
        self.assertEqual(sent[1]["type"], "http.response.body")
        self.assertIn(b'"http_version": "3"', sent[1]["body"])
        self.assertIn(b'"path": "/inspect"', sent[1]["body"])
        self.assertIn(b'"query_string": "payload=hello"', sent[1]["body"])
