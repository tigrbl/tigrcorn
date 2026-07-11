from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
from tigrcorn_observability.metrics import Metrics
from tigrcorn_protocols.webtransport.negotiation import negotiate_profiles, settings_for_profiles
from tigrcorn_protocols.http3.handler.session import HTTP3Session
from tigrcorn_protocols.http3.handler.webtransport_support import HTTP3WebTransportSupportMixin
from tigrcorn_protocols.http3.state import HTTP3UniStreamState
from tigrcorn_transports.quic.connection import QuicConnection


PROFILES = ("draft02", "draft13", "ietf-current")


def test_multiversion_settings_advertise_each_profile_and_shared_settings_once() -> None:
    settings = settings_for_profiles(PROFILES, max_sessions=8)
    assert settings == {
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
        SETTING_ENABLE_WEBTRANSPORT: 1,
        SETTING_WT_MAX_SESSIONS: 8,
        SETTING_WT_ENABLED: 1,
    }


def test_profile_selection_prefers_preferred_then_configured_order() -> None:
    peer = {
        SETTING_ENABLE_WEBTRANSPORT: 1,
        SETTING_WT_MAX_SESSIONS: 4,
    }
    preferred = negotiate_profiles(PROFILES, "draft13", peer)
    fallback = negotiate_profiles(PROFILES, "ietf-current", peer)
    assert preferred.selected_profile == "draft13"
    assert fallback.selected_profile == "draft02"
    assert fallback.mutual_profiles == ("draft02", "draft13")


def test_profile_selection_fails_closed_for_no_overlap_and_malformed_values() -> None:
    no_overlap = negotiate_profiles(PROFILES, "ietf-current", {})
    malformed = negotiate_profiles(PROFILES, "ietf-current", {SETTING_ENABLE_WEBTRANSPORT: 0})
    assert no_overlap.selected_profile is None
    assert no_overlap.failure_reason == "no-mutual-profile"
    assert malformed.selected_profile is None
    assert malformed.failure_reason == "malformed-setting:0x2b603742"


def test_profile_metrics_have_a_bounded_label_surface() -> None:
    metrics = Metrics()
    for profile in PROFILES:
        metrics.webtransport_profile_selected(profile)
    metrics.webtransport_profile_selected("unbounded-user-value")
    metrics.webtransport_negotiation_rejected_observed()
    snapshot = metrics.snapshot()
    assert snapshot["webtransport_profile_draft02_selected"] == 1
    assert snapshot["webtransport_profile_draft13_selected"] == 1
    assert snapshot["webtransport_profile_ietf_current_selected"] == 1
    assert snapshot["webtransport_negotiation_rejected"] == 1
    assert "unbounded-user-value" not in metrics.render_prometheus()


def test_selected_profile_is_frozen_for_connection_lifetime() -> None:
    class Handler(HTTP3WebTransportSupportMixin):
        metrics = None
        connection_inventory = None

        def __init__(self):
            self.config = SimpleNamespace(webtransport=SimpleNamespace(
                profiles=list(PROFILES),
                preferred_profile="ietf-current",
                max_sessions=8,
            ))
            self.events = []

        def trace_webtransport(self, event, **fields):
            self.events.append((event, fields))

        def _trace_session_fields(self, session):
            return {}

    session = HTTP3Session(
        addr=("127.0.0.1", 4433),
        quic=QuicConnection(is_client=False, secret=b"test-secret", local_cid=b"frozen01"),
    )
    session.h3.state.remote_control_stream_id = 2
    session.h3.state.uni_streams[2] = HTTP3UniStreamState(
        stream_id=2,
        stream_type=0,
        settings_received=True,
    )
    session.h3.state.remote_settings = {SETTING_ENABLE_WEBTRANSPORT: 1}
    handler = Handler()
    first = handler._ensure_webtransport_negotiation(session)
    session.h3.state.remote_settings = {SETTING_WT_ENABLED: 1}
    second = handler._ensure_webtransport_negotiation(session)
    assert first is second
    assert second.selected_profile == "draft02"
    assert len(handler.events) == 1


async def _exercise_multiversion_listener() -> None:
    app_connects: list[str] = []

    async def app(scope, receive, send):
        connect = await receive()
        app_connects.append(connect["session_id"])
        await send({"type": "webtransport.accept", "session_id": connect["session_id"]})
        while True:
            event = await receive()
            if event["type"] == "webtransport.stream.receive":
                await send({
                    "type": "webtransport.stream.send",
                    "session_id": connect["session_id"],
                    "stream_id": event["stream_id"],
                    "data": b"multi:" + event["data"],
                    "more": False,
                })
            elif event["type"] in {"webtransport.close", "webtransport.disconnect"}:
                return

    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = Path(tmpdir) / "cert.pem"
        keyfile = Path(tmpdir) / "key.pem"
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
            webtransport_profiles=list(PROFILES),
            webtransport_preferred_profile="ietf-current",
        )
        assert config.listeners[0].alpn_protocols == ["h3"]
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
        try:
            results = []
            for index, profile in enumerate(PROFILES):
                results.append(await probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    profile=profile,
                    local_cid=f"wtmulti{index}".encode(),
                    payload=profile.encode(),
                ))
                await asyncio.sleep(0.05)
            traces = list(server._datagram_handlers[0].webtransport_trace)
            inventory = server.connection_inventory()
        finally:
            await server.close()

    assert [result.status for result in results] == [200, 200, 200]
    assert [result.body for result in results] == [
        b"multi:draft02",
        b"multi:draft13",
        b"multi:ietf-current",
    ]
    selected = [row["selected_profile"] for row in traces if row["event"] == "webtransport.profile.selected"]
    assert selected == list(PROFILES)
    inventory_profiles = {
        row["metadata"].get("webtransport_profile")
        for row in inventory["sessions"].values()
        if row["kind"] == "webtransport"
    }
    assert inventory_profiles == set(PROFILES)
    assert len(app_connects) == 3


def test_each_profile_succeeds_on_separate_connections_to_one_listener() -> None:
    asyncio.run(_exercise_multiversion_listener())


async def _exercise_rejection(
    *,
    profile: str = "ietf-current",
    send_settings: bool,
    connect_token: bytes | None,
    expected_status: int,
    profile_setting_value: int = 1,
    extra_connect_headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    app_started = False

    async def app(scope, receive, send):
        nonlocal app_started
        app_started = True

    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = Path(tmpdir) / "cert.pem"
        keyfile = Path(tmpdir) / "key.pem"
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
            webtransport_profiles=list(PROFILES),
            webtransport_preferred_profile="ietf-current",
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info("sockname")[1]
        try:
            response = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                profile=profile,
                connect_token=connect_token,
                send_settings=send_settings,
                profile_setting_value=profile_setting_value,
                extra_connect_headers=extra_connect_headers,
                local_cid=b"wtcross1",
            )
        finally:
            await server.close()

    assert response.status == expected_status
    assert app_started is False


def test_cross_profile_connect_is_rejected_before_application_start() -> None:
    asyncio.run(_exercise_rejection(
        send_settings=True,
        connect_token=b"webtransport",
        expected_status=501,
    ))


def test_connect_before_peer_settings_is_rejected_before_application_start() -> None:
    asyncio.run(_exercise_rejection(
        send_settings=False,
        connect_token=None,
        expected_status=425,
    ))


def test_no_overlap_is_rejected_before_application_start() -> None:
    asyncio.run(_exercise_rejection(
        profile="unsupported",
        send_settings=True,
        connect_token=b"webtransport-h3",
        expected_status=421,
    ))


def test_malformed_profile_setting_is_rejected_before_application_start() -> None:
    asyncio.run(_exercise_rejection(
        profile="draft02",
        send_settings=True,
        connect_token=b"webtransport",
        expected_status=421,
        profile_setting_value=0,
    ))


def test_cross_profile_version_header_is_rejected_before_application_start() -> None:
    asyncio.run(_exercise_rejection(
        profile="ietf-current",
        send_settings=True,
        connect_token=b"webtransport-h3",
        expected_status=421,
        extra_connect_headers=((b"sec-webtransport-http3-draft02", b"1"),),
    ))
