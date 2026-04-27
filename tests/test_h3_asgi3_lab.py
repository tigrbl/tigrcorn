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
        self.assertIn("--protocol webtransport", compose)
        self.assertIn("--http 3", compose)
        self.assertIn("--webtransport-path /wt", compose)
        self.assertIn('"8445:8445/udp"', compose)
        self.assertIn("tigrcorn-h3-uix:", compose)
        self.assertIn("examples.h3_asgi3_lab.uix_server", compose)
        self.assertIn('"8091:8090/tcp"', compose)

    def test_uix_uses_browser_webtransport_certificate_hashes(self) -> None:
        html = (EXAMPLE / "uix" / "index.html").read_text(encoding="utf-8")
        js = (EXAMPLE / "uix" / "main.js").read_text(encoding="utf-8")

        self.assertIn('value="https://localhost:8445/wt"', html)
        self.assertIn("new WebTransport(endpoint.value, options)", js)
        self.assertIn("serverCertificateHashes", js)
        self.assertIn('/cert-hash.json', js)


class H3Asgi3LabAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_webtransport_session_accepts_and_echoes_stream_payload(self) -> None:
        sent: list[dict[str, object]] = []
        events = iter(
            [
                {
                    "type": "webtransport.stream.receive",
                    "session_id": "session-1",
                    "stream_id": "stream-1",
                    "data": b"hello",
                },
                {"type": "webtransport.close", "session_id": "session-1"},
            ]
        )

        async def receive() -> dict[str, object]:
            return next(events)

        async def send(event: dict[str, object]) -> None:
            sent.append(event)

        await app(
            {
                "type": "webtransport",
                "path": "/wt",
                "extensions": {"tigrcorn.unit": {"session_id": "session-1"}},
            },
            receive,
            send,
        )

        self.assertEqual(sent[0]["type"], "webtransport.accept")
        self.assertEqual(sent[1]["type"], "webtransport.datagram.send")
        self.assertEqual(sent[2]["type"], "webtransport.stream.send")
        self.assertIn(b'"event": "stream.echo"', sent[2]["data"])
        self.assertIn(b'"payload": "hello"', sent[2]["data"])
