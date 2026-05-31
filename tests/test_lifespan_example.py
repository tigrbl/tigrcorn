import importlib
import json
import unittest

from tigrcorn.protocols.lifespan.driver import LifespanManager


class LifespanExampleTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_example_exposes_startup_state(self):
        module = importlib.reload(importlib.import_module("examples.lifespan.app"))

        manager = LifespanManager(module.app, mode="on")
        await manager.startup()
        try:
            response = await self._request(module.app, "/state")
            self.assertEqual(response["status"], 200)
            state = json.loads(response["body"].decode("utf-8"))
            self.assertTrue(state["ready"])
            self.assertEqual(state["startup_count"], 1)
            self.assertEqual(state["shutdown_count"], 0)
            self.assertEqual(state["last_event"], "lifespan.startup")
        finally:
            await manager.shutdown()

        self.assertFalse(module.STATE["ready"])
        self.assertEqual(module.STATE["shutdown_count"], 1)
        self.assertEqual(module.STATE["last_event"], "lifespan.shutdown")

    async def test_lifespan_example_healthz_uses_readiness(self):
        module = importlib.reload(importlib.import_module("examples.lifespan.app"))

        response = await self._request(module.app, "/healthz")
        self.assertEqual(response["status"], 503)
        self.assertEqual(response["body"], b"not ready\n")

    async def test_lifespan_example_serves_uix_assets(self):
        module = importlib.reload(importlib.import_module("examples.lifespan.app"))

        index = await self._request(module.app, "/uix/")
        self.assertEqual(index["status"], 200)
        self.assertIn(b"Tigrcorn Lifespan UIX", index["body"])

        script = await self._request(module.app, "/uix/main.js")
        self.assertEqual(script["status"], 200)
        self.assertIn(b"refreshState", script["body"])

    async def _request(self, app, path):
        sent = []
        received = [{"type": "http.request", "body": b"", "more_body": False}]

        async def receive():
            return received.pop(0)

        async def send(message):
            sent.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.5"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 8000),
            },
            receive,
            send,
        )
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return {"status": start["status"], "headers": start["headers"], "body": body}
