from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from examples.http2_asgi3_demo.app import app
from examples.http2_asgi3_demo.h2_client import H2PriorKnowledgeClient
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "http2_asgi3_demo"


class HTTP2ASGI3DemoConfigTests(unittest.TestCase):
    def test_compose_runs_tigrcorn_http2_app_and_uix_client(self) -> None:
        compose = (DEMO / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("tigrcorn-h2-app:", compose)
        self.assertIn("tigrcorn-h2.toml", compose)
        self.assertIn("--app-interface", compose)
        self.assertIn("asgi3", compose)
        self.assertIn("--http", compose)
        self.assertIn('"2"', compose)
        self.assertIn("--protocol", compose)
        self.assertIn("http2", compose)
        self.assertIn("--http2-max-concurrent-streams", compose)
        self.assertIn("--http2-adaptive-window", compose)
        self.assertIn('"8002:8000/tcp"', compose)
        self.assertIn("tigrcorn-h2-uix:", compose)
        self.assertIn("examples.http2_asgi3_demo.client_server", compose)
        self.assertIn('"8089:8080/tcp"', compose)
        config = (DEMO / "tigrcorn-h2.toml").read_text(encoding="utf-8")
        self.assertIn("enable_h2c = true", config)

    def test_uix_mentions_core_experiments(self) -> None:
        html = (DEMO / "client" / "index.html").read_text(encoding="utf-8")
        js = (DEMO / "client" / "main.js").read_text(encoding="utf-8")

        self.assertIn("HTTP/2 Lab", html)
        self.assertIn("Streaming response", html)
        self.assertIn("Multiplex 6", html)
        self.assertIn("/api/multiplex?count=6&path=/scope", js)


class HTTP2ASGI3DemoRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        config = build_config(
            host="127.0.0.1",
            port=0,
            lifespan="off",
            http_versions=["2"],
            protocols=["http2"],
            http2_max_concurrent_streams=16,
        )
        self.server = TigrCornServer(app, config)
        await self.server.start()
        listener = self.server._listeners[0]
        self.port = listener.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self) -> None:
        await self.server.close()

    async def test_h2_prior_knowledge_client_observes_asgi3_http2_scope(self) -> None:
        response = await asyncio.to_thread(
            H2PriorKnowledgeClient("127.0.0.1", self.port, authority="localhost").request,
            "GET",
            "/",
        )

        self.assertEqual(response.status, 200)
        self.assertIn(b'"http_version": "2"', response.body)

    async def test_h2_prior_knowledge_client_posts_body_through_asgi_receive(self) -> None:
        response = await asyncio.to_thread(
            H2PriorKnowledgeClient("127.0.0.1", self.port, authority="localhost").request,
            "POST",
            "/echo",
            b"demo-body",
        )

        self.assertEqual(response.status, 200)
        self.assertIn(b'"body_text": "demo-body"', response.body)

    async def test_h2_client_multiplexes_multiple_streams_on_one_connection(self) -> None:
        responses = await asyncio.to_thread(
            H2PriorKnowledgeClient("127.0.0.1", self.port, authority="localhost").multiplex_get,
            ["/scope?item=1", "/scope?item=2", "/scope?item=3"],
        )

        self.assertEqual([response.status for response in responses], [200, 200, 200])
        self.assertEqual([response.stream_id for response in responses], [1, 3, 5])
        self.assertTrue(all(b'"http_version": "2"' in response.body for response in responses))


if __name__ == "__main__":
    unittest.main()
