from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from tigrcorn_config.load import build_config
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_runtime.embedded import EmbeddedServer
from tigrcorn_runtime.server.runner import TigrCornServer


async def _app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] == "http":
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})


def _config(**kwargs):
    kwargs.setdefault("app", None)
    kwargs.setdefault("port", 0)
    kwargs.setdefault("http_versions", ["1.1"])
    kwargs.setdefault("websocket", False)
    return build_config(**kwargs)


def _server(**kwargs) -> TigrCornServer:
    return TigrCornServer(_app, _config(**kwargs))


def _by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in snapshot["resources"]}


def test_embedded_resource_ownership_model_shape() -> None:
    snapshot = _server(ssl_certfile="server.crt", ssl_keyfile="server.key").resource_ownership()
    kinds = {item["kind"] for item in snapshot["resources"]}

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["owner"] == "tigrcorn"
    assert {"listener", "socket", "transport", "tls_context", "event_loop", "worker_pool", "telemetry_exporter"} <= kinds
    for resource in snapshot["resources"]:
        assert {"id", "kind", "owner", "caller_owned", "active", "close_action"} <= set(resource)


def test_embedded_resource_owner_ids_deterministic() -> None:
    first = _server(ssl_certfile="server.crt", ssl_keyfile="server.key").resource_ownership()
    second = _server(ssl_certfile="server.crt", ssl_keyfile="server.key").resource_ownership()

    assert first == second
    assert [item["id"] for item in first["resources"]] == sorted(item["id"] for item in first["resources"])
    assert json.loads(json.dumps(first, sort_keys=True)) == first


def test_embedded_resource_shutdown_ownership() -> None:
    async def scenario() -> tuple[dict[str, Any], dict[str, Any]]:
        server = _server()
        await server.start()
        active = server.resource_ownership()
        await server.close()
        closed = server.resource_ownership()
        return active, closed

    active, closed = asyncio.run(scenario())

    assert active["active"] is True
    assert _by_id(active)["listener:0"]["active"] is True
    assert _by_id(active)["socket:0"]["active"] is True
    assert closed["active"] is False
    assert _by_id(closed)["listener:0"]["active"] is False
    assert _by_id(closed)["socket:0"]["active"] is False


def test_embedded_resource_restart_reload_ownership() -> None:
    async def scenario() -> tuple[TigrCornServer, TigrCornServer, list[str], list[str]]:
        embedded = EmbeddedServer(_app, _config())
        first = await embedded.start()
        first_ids = [item["id"] for item in embedded.resource_ownership()["resources"]]
        await embedded.close()
        second = await embedded.start()
        second_ids = [item["id"] for item in embedded.resource_ownership()["resources"]]
        await embedded.close()
        return first, second, first_ids, second_ids

    first, second, first_ids, second_ids = asyncio.run(scenario())

    assert first is not second
    assert first._listeners == []
    assert second._listeners == []
    assert first_ids == second_ids


def test_embedded_resource_telemetry_exporter_flush() -> None:
    class FakeExporter:
        def __init__(self) -> None:
            self.stopped_with_metrics = False

        async def stop(self, metrics=None) -> None:
            self.stopped_with_metrics = metrics is not None

    async def scenario() -> FakeExporter:
        server = _server()
        exporter = FakeExporter()
        server._statsd_exporter = exporter  # type: ignore[assignment]
        await server.close()
        return exporter

    exporter = asyncio.run(scenario())

    assert exporter.stopped_with_metrics is True


def test_embedded_resource_double_close_prevention() -> None:
    async def scenario() -> tuple[int, dict[str, Any]]:
        server = _server()
        await server.start()
        await server.close()
        await server.close()
        return len(server._listeners), server.resource_ownership()

    listener_count, snapshot = asyncio.run(scenario())

    assert listener_count == 0
    assert snapshot["active"] is False
    assert _by_id(snapshot)["listener:0"]["active"] is False


def test_embedded_resource_failure_cleanup() -> None:
    class TrackingListener:
        def __init__(self) -> None:
            self.closed = False

        async def start(self, callback: Callable[..., Awaitable[None]]) -> None:
            return None

        async def close(self) -> None:
            self.closed = True

    class FailingListener:
        async def start(self, callback: Callable[..., Awaitable[None]]) -> None:
            raise RuntimeError("listener boom")

        async def close(self) -> None:
            return None

    class FailingServer(TigrCornServer):
        def __init__(self) -> None:
            config = ServerConfig(listeners=[ListenerConfig(kind="inproc"), ListenerConfig(kind="inproc")])
            super().__init__(_app, config)
            self.tracking = TrackingListener()
            self.calls = 0

        async def _make_listener(self, cfg):
            self.calls += 1
            if self.calls == 1:
                return self.tracking
            return FailingListener()

    async def scenario() -> FailingServer:
        server = FailingServer()
        with pytest.raises(RuntimeError, match="listener boom"):
            await server.start()
        return server

    server = asyncio.run(scenario())

    assert server.tracking.closed is True
    assert server._listeners == []
    assert server.resource_ownership()["active"] is False


def test_embedded_resource_external_loop_not_closed() -> None:
    async def scenario() -> tuple[bool, bool]:
        loop = asyncio.get_running_loop()
        server = _server()
        before = loop.is_closed()
        await server.start()
        await server.close()
        return before, loop.is_closed()

    before, after = asyncio.run(scenario())

    assert before is False
    assert after is False


def test_embedded_resource_worker_failure_releases_listeners() -> None:
    async def scenario() -> tuple[int, dict[str, Any]]:
        server = _server(config={"process": {"limit_max_requests": 0}})
        await server.start()
        server.request_shutdown()
        await server.close()
        return len(server._listeners), server.resource_ownership()

    listener_count, snapshot = asyncio.run(scenario())

    assert listener_count == 0
    assert snapshot["active"] is False
    assert _by_id(snapshot)["listener:0"]["active"] is False
