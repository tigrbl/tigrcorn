from __future__ import annotations

import json
import unittest

from examples.websocket_uix_demo.app import app


class WebSocketUixDemoTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_endpoint(self) -> None:
        sent = []
        received = [{"type": "http.request", "body": b"", "more_body": False}]

        async def receive():
            return received.pop(0)

        async def send(event):
            sent.append(event)

        await app({"type": "http", "path": "/health"}, receive, send)

        self.assertEqual(sent[0]["type"], "http.response.start")
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(json.loads(sent[1]["body"]), {"ok": True, "service": "tigrcorn-websocket-uix-demo"})

    async def test_echoes_json_messages(self) -> None:
        sent = []
        received = [
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": json.dumps({"action": "echo", "text": "hello"})},
            {"type": "websocket.disconnect", "code": 1000},
        ]

        async def receive():
            return received.pop(0)

        async def send(event):
            sent.append(event)

        await app({"type": "websocket", "path": "/ws"}, receive, send)

        self.assertEqual(sent[0]["type"], "websocket.accept")
        events = [json.loads(event["text"])["event"] for event in sent if event["type"] == "websocket.send"]
        self.assertIn("system", events)
        self.assertIn("echo", events)


if __name__ == "__main__":
    unittest.main()
