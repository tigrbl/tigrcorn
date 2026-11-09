from __future__ import annotations

import asyncio
import json

import pytest

from tigrcorn_config.load import build_config
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


def _server(**kwargs) -> TigrCornServer:
    kwargs.setdefault("http_versions", ["1.1"])
    kwargs.setdefault("websocket", False)
    kwargs.setdefault("port", 0)
    config = build_config(app=None, **kwargs)
    return TigrCornServer(_app, config)


def test_runtime_describe_public_api_shape() -> None:
    payload = _server().describe()

    assert payload["schema_version"] == "1.0"
    assert payload["active"] is False
    assert payload["runtime"] == "auto"
    assert payload["profile"] == "default"
    assert payload["listeners"][0]["id"] == "listener:0"
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_runtime_describe_empty_server_state() -> None:
    server = _server()
    before = server.describe()
    after = server.describe()

    assert server._listeners == []
    assert before == after
    assert before["active_protocols"] == []
    assert before["active_transports"] == []
    assert before["connection_inventory"]["counts"] == {
        "active_connections": 0,
        "active_peers": 0,
        "active_sessions": 0,
        "connections": 0,
        "peers": 0,
        "sessions": 0,
    }
    assert before["listeners"][0]["active"] is False
    assert before["listeners"][0]["bound_endpoint"] is None


def test_runtime_describe_active_listeners() -> None:
    async def scenario() -> dict[str, object]:
        server = _server()
        await server.start()
        try:
            return server.describe()
        finally:
            await server.close()

    payload = asyncio.run(scenario())

    listener = payload["listeners"][0]
    assert payload["active"] is True
    assert listener["active"] is True
    assert listener["kind"] == "tcp"
    assert listener["label"].startswith("127.0.0.1:")
    assert listener["bound_endpoint"] is not None
    assert payload["connection_inventory"]["counts"]["connections"] == 0


def test_runtime_describe_records_http11_connection_inventory() -> None:
    async def scenario() -> dict[str, object]:
        server = _server()
        await server.start()
        try:
            port = server._listeners[0].server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /inventory HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer.drain()
            await asyncio.wait_for(reader.read(4096), timeout=2.0)
            writer.close()
            await writer.wait_closed()
            await asyncio.sleep(0)
            return server.describe()["connection_inventory"]
        finally:
            await server.close()

    inventory = asyncio.run(scenario())

    assert inventory["counts"]["connections"] == 1
    connection = next(iter(inventory["connections"].values()))
    assert connection["transport"] == "tcp"
    assert connection["state"] == "closed"
    assert connection["counters"]["requests"] == 1
    assert connection["session_ids"]
    session = next(iter(inventory["sessions"].values()))
    assert session["kind"] == "http-request"
    assert session["state"] == "closed"


def test_runtime_describe_protocol_transport_tls_state() -> None:
    server = _server(
        ssl_certfile="server.crt",
        ssl_keyfile="server.key",
        ssl_ca_certs="ca.pem",
        ssl_require_client_cert=True,
    )
    payload = server.describe()
    listener = payload["listeners"][0]

    assert listener["protocols"] == ["http1"]
    assert payload["configured_protocols"] == ["http1"]
    assert payload["configured_transports"] == ["tcp"]
    assert listener["tls"]["enabled"] is True
    assert listener["tls"]["client_cert_required"] is True
    assert listener["tls"]["certfile"] == "<redacted>"
    assert listener["tls"]["keyfile"] == "<redacted>"
    assert listener["tls"]["ca_certs"] == "<redacted>"


def test_runtime_describe_profile_worker_observability_state() -> None:
    server = _server(
        profile="strict-h1-origin",
        runtime="asyncio",
        config={
            "process": {"workers": 2, "worker_class": "asyncio"},
            "metrics": {"enabled": True, "bind": "127.0.0.1:0", "statsd_host": "statsd://127.0.0.1:8125"},
            "logging": {"structured": True},
        },
    )
    payload = server.describe()

    assert payload["profile"] == "strict-h1-origin"
    assert payload["worker"] == {"count": 2, "class": "process", "runtime": "asyncio"}
    assert payload["observability"]["metrics_enabled"] is True
    assert payload["observability"]["metrics_bind"] == "127.0.0.1:0"
    assert payload["observability"]["statsd_enabled"] is True
    assert payload["observability"]["structured_logging"] is True


def test_runtime_describe_redacts_sensitive_material() -> None:
    server = _server(
        ssl_certfile="C:/secret/server.crt",
        ssl_keyfile="C:/secret/server.key",
        ssl_keyfile_password="super-secret-password",
        ssl_ca_certs="C:/secret/ca.pem",
        quic_secret=b"quic-secret-token",
    )
    rendered = json.dumps(server.describe(), sort_keys=True)

    assert "super-secret-password" not in rendered
    assert "quic-secret-token" not in rendered
    assert "C:/secret" not in rendered
    assert "<redacted>" in rendered


def test_runtime_describe_distinguishes_capable_from_active() -> None:
    payload = _server(http_versions=["1.1"]).describe()

    assert "http3" in payload["capabilities"]["protocols"]
    assert "quic" in payload["capabilities"]["transports"]
    assert payload["configured_protocols"] == ["http1"]
    assert payload["active_protocols"] == []
    assert payload["active_transports"] == []


def test_runtime_describe_fails_closed_on_invalid_profile() -> None:
    with pytest.raises(ValueError, match="unknown blessed profile"):
        build_config(profile="does-not-exist", app=None)


def test_runtime_describe_stable_key_ordering() -> None:
    server = _server()
    first = json.dumps(server.describe(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(server.describe(), sort_keys=True, separators=(",", ":"))

    assert first == second


def test_embedded_server_describe_delegates_without_starting() -> None:
    embedded = EmbeddedServer(_app, build_config(app=None, port=0, http_versions=["1.1"], websocket=False))

    payload = embedded.describe()

    assert payload["active"] is False
    assert payload["listeners"][0]["active"] is False
    assert embedded.listeners == []
