from __future__ import annotations

import json
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from examples.wss_asgi3_lab.app import app


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "wss_asgi3_lab"


def test_wss_asgi3_compose_declares_server_and_uix_services() -> None:
    compose = (EXAMPLE / "docker-compose.yml").read_text(encoding="utf-8")

    assert "tigrcorn-wss-asgi3:" in compose
    assert "tigrcorn-wss-uix:" in compose
    assert "tigrcorn-wss-asgi3-lab:local" in compose
    assert "tigrcorn-wss-uix-lab:local" in compose
    assert '"8443:8443/tcp"' in compose
    assert '"8093:8080/tcp"' in compose
    assert 'TIGRCORN_WSS_URL: "wss://localhost:8443/ws"' in compose


def test_wss_asgi3_dockerfile_uses_tigrcorn_tls_websocket_flags() -> None:
    dockerfile = (EXAMPLE / "Dockerfile").read_text(encoding="utf-8")

    assert "--app-interface" in dockerfile
    assert "asgi3" in dockerfile
    assert "--protocol" in dockerfile
    assert "websocket" in dockerfile
    assert "--ssl-certfile" in dockerfile
    assert "cert_setup" in dockerfile
    assert "/certs/server-cert.pem" in dockerfile
    assert "--ssl-keyfile" in dockerfile
    assert "--websocket-compression" in dockerfile
    assert "permessage-deflate" in dockerfile
    assert "-e pkgs/tigrcorn-certification" in dockerfile


class WssAsgi3AppTests(IsolatedAsyncioTestCase):
    async def test_health_response_reports_wss_endpoint(self) -> None:
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        await app({"type": "http", "path": "/health", "extensions": {}}, receive, send)

        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 200
        body = json.loads(sent[1]["body"])
        assert body["wss_url"] == "wss://localhost:8443/ws"
        assert body["interface"] == "asgi3"

    async def test_websocket_echoes_text_messages(self) -> None:
        events = iter(
            [
                {"type": "websocket.connect"},
                {"type": "websocket.receive", "text": "hello"},
                {"type": "websocket.disconnect"},
            ]
        )
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, object]:
            return next(events)

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        await app(
            {
                "type": "websocket",
                "path": "/ws",
                "query_string": b"room=demo&name=tester",
                "extensions": {"tigrcorn.security": {"tls": True}},
            },
            receive,
            send,
        )

        assert sent[0]["type"] == "websocket.accept"
        assert sent[0]["subprotocol"] == "tigrcorn.lab.v1"
        payloads = [json.loads(item["text"]) for item in sent if item.get("type") == "websocket.send"]
        assert payloads[0]["kind"] == "ready"
        assert payloads[1]["kind"] == "echo"
        assert payloads[1]["payload"] == "hello"
