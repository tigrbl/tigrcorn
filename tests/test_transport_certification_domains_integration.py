from __future__ import annotations

import asyncio

import pytest

from tigrcorn_config.load import build_config
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_runtime.server.runner import TigrCornServer
from tigrcorn_transports.registry import TransportDomainError


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


def _tcp_server(*, profile: str | None = None) -> TigrCornServer:
    config = build_config(app=None, port=0, http_versions=["1.1"], websocket=False, profile=profile)
    return TigrCornServer(_app, config)


def _entry(payload: dict, domain_id: str) -> dict:
    return next(item for item in payload["diagnostics"] if item["domain_id"] == domain_id)


def test_runtime_listener_registers_transport_domain_accounting() -> None:
    async def scenario() -> dict:
        server = _tcp_server()
        await server.start()
        try:
            return server.describe()["transport_domains"]
        finally:
            await server.close()

    diagnostics = asyncio.run(scenario())

    listener = _entry(diagnostics, "listener")
    tcp = _entry(diagnostics, "tcp")
    assert listener["carrier_state"] == "active"
    assert listener["resource_counters"]["connections"] == 1
    assert tcp["carrier_state"] == "active"
    assert tcp["resource_counters"]["connections"] == 1
    assert tcp["resource_counters"]["streams"] == 1


def test_transport_diagnostics_reflect_started_tcp_listener() -> None:
    async def scenario() -> dict:
        server = _tcp_server()
        await server.start()
        try:
            return server.transport_domain_diagnostics()
        finally:
            await server.close()

    diagnostics = asyncio.run(scenario())
    tcp = _entry(diagnostics, "tcp")

    assert diagnostics["registry_id"] == "tigrcorn.transport.diagnostics"
    assert tcp["transport_kind"] == "tcp"
    assert tcp["certification_state"] == "certified"
    assert tcp["endpoint_identity"] is not None
    assert tcp["resource_counters"]["connections"] == 1


def test_strict_profile_rejects_runtime_listener_domain() -> None:
    config = ServerConfig(
        app=build_config(app=None, profile="strict-h1-origin").app,
        listeners=[ListenerConfig(kind="udp", host="127.0.0.1", port=0, protocols=["quic", "http3"])],
    )
    server = TigrCornServer(_app, config)

    with pytest.raises(TransportDomainError, match="udp|quic"):
        asyncio.run(server.start())


def test_quic_listener_remains_uncertified_without_quic_evidence() -> None:
    config = ServerConfig(
        listeners=[ListenerConfig(kind="udp", host="127.0.0.1", port=0, protocols=["quic", "http3"])],
    )
    server = TigrCornServer(_app, config)

    async def scenario() -> dict:
        await server.start()
        try:
            return server.transport_domain_diagnostics()
        finally:
            await server.close()

    diagnostics = asyncio.run(scenario())
    quic = _entry(diagnostics, "quic")

    assert quic["carrier_state"] == "active"
    assert quic["certification_state"] == "implemented"
    assert quic["resource_counters"]["connections"] == 1
