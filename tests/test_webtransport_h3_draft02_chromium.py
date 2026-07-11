from __future__ import annotations

import tempfile
import asyncio
from pathlib import Path

from tests.fixtures_third_party.wt_stream_client import probe_wt_stream
from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3.codec import (
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_H3_DATAGRAM,
    SETTING_WT_ENABLED,
    SETTING_WT_MAX_SESSIONS,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic.handshake import generate_self_signed_certificate
from tigrcorn_protocols.webtransport.profiles import (
    DRAFT02_PROFILE,
    missing_request_requirement,
)


def test_draft02_profile_uses_chromium_setting_and_connect_contract() -> None:
    settings = DRAFT02_PROFILE.settings_dict()
    assert settings == {
        SETTING_ENABLE_WEBTRANSPORT: 1,
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
    }
    assert SETTING_WT_ENABLED not in settings
    assert SETTING_WT_MAX_SESSIONS not in settings
    assert DRAFT02_PROFILE.connect_token == b"webtransport"
    assert DRAFT02_PROFILE.requires_reset_stream_at is False


def test_draft02_connect_requires_exact_chromium_marker() -> None:
    marker = b"sec-webtransport-http3-draft02"
    assert missing_request_requirement(DRAFT02_PROFILE, {marker: b"1"}) is None
    assert missing_request_requirement(DRAFT02_PROFILE, {}) == f"header:{marker.decode()}"
    assert missing_request_requirement(DRAFT02_PROFILE, {marker: b"0"}) == f"header:{marker.decode()}"


async def _draft02_live_connect_streams_and_datagram_roundtrip() -> None:
    app_events: list[str] = []

    async def app(scope, receive, send):
        app_events.append(scope["type"])
        connect = await receive()
        session_id = connect["session_id"]
        await send({"type": "webtransport.accept", "session_id": session_id})
        while True:
            event = await receive()
            app_events.append(event["type"])
            if event["type"] == "webtransport.stream.receive":
                if event.get("stream_direction") == "client_to_server":
                    continue
                await send({
                    "type": "webtransport.stream.send",
                    "session_id": session_id,
                    "stream_id": event["stream_id"],
                    "data": b"draft02:" + event["data"],
                    "more": False,
                })
            elif event["type"] == "webtransport.datagram.receive":
                await send({
                    "type": "webtransport.datagram.send",
                    "session_id": session_id,
                    "datagram_id": event["datagram_id"],
                    "data": b"draft02-dg:" + event["data"],
                })
            elif event["type"] in {"webtransport.close", "webtransport.disconnect"}:
                return

    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = Path(tmpdir) / "server-cert.pem"
        keyfile = Path(tmpdir) / "server-key.pem"
        certfile.write_bytes(cert_pem)
        keyfile.write_bytes(key_pem)
        config = build_config(
            transport="udp",
            host="127.0.0.1",
            port=0,
            lifespan="off",
            http_versions=["3"],
            protocols=["webtransport"],
            ssl_certfile=str(certfile),
            ssl_keyfile=str(keyfile),
            webtransport_path="/wt",
            webtransport_origins=["https://localhost:8088"],
            webtransport_profiles=["chromium"],
            webtransport_preferred_profile="chromium",
        )
        assert config.listeners[0].alpn_protocols == ["h3"]
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
        try:
            response = await probe_wt_stream(
                "127.0.0.1",
                port,
                payload=b"hello",
                trusted_certificates=[cert_pem],
                child_payloads=(b"one", b"two"),
                datagram_payload=b"ping",
                send_unidi=True,
                profile="chromium",
                local_cid=b"wtdraft2",
            )
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()

    assert response.status == 200
    assert response.header_map()[b"sec-webtransport-http3-draft"] == b"draft02"
    assert response.remote_settings[SETTING_ENABLE_WEBTRANSPORT] == 1
    assert SETTING_WT_ENABLED not in response.remote_settings
    assert SETTING_WT_MAX_SESSIONS not in response.remote_settings
    assert response.stream_bodies[4] == b"draft02:one"
    assert response.stream_bodies[8] == b"draft02:two"
    assert response.datagram_body == b"draft02-dg:ping"
    assert "webtransport" in app_events
    connect_rows = [row for row in trace if row["event"] == "webtransport.connect.start"]
    assert connect_rows[0]["profile"] == "draft02"
    assert connect_rows[0]["setting_id"] == "0x2b603742"


def test_draft02_live_connect_streams_and_datagram_roundtrip() -> None:
    asyncio.run(_draft02_live_connect_streams_and_datagram_roundtrip())


async def _draft02_missing_marker_is_rejected_before_app_start() -> None:
    app_started = False

    async def app(scope, receive, send):
        nonlocal app_started
        app_started = True

    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = Path(tmpdir) / "server-cert.pem"
        keyfile = Path(tmpdir) / "server-key.pem"
        certfile.write_bytes(cert_pem)
        keyfile.write_bytes(key_pem)
        config = build_config(
            transport="udp",
            host="127.0.0.1",
            port=0,
            lifespan="off",
            http_versions=["3"],
            protocols=["webtransport"],
            ssl_certfile=str(certfile),
            ssl_keyfile=str(keyfile),
            webtransport_profiles=["chromium"],
            webtransport_preferred_profile="chromium",
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
        try:
            response = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                profile="chromium",
                draft_marker=None,
                local_cid=b"wtd2bad1",
            )
        finally:
            await server.close()

    assert response.status == 421
    assert app_started is False


def test_draft02_missing_marker_is_rejected_before_app_start() -> None:
    asyncio.run(_draft02_missing_marker_is_rejected_before_app_start())
