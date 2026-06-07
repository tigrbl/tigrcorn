from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path

from tests.fixtures_third_party.wt_stream_client import probe_wt_stream
from tigrcorn.config.load import build_config
from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import (
    FRAME_SETTINGS,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_H3_DATAGRAM,
    STREAM_TYPE_CONTROL,
    encode_frame,
    encode_settings,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.utils.bytes import encode_quic_varint


async def _wt_child_stream_echo_app(scope, receive, send, *, stream_received=None, stream_sent=None) -> None:
    assert scope["type"] == "webtransport"
    connect = await receive()
    assert connect["type"] == "webtransport.connect"
    session_id = connect["session_id"]
    await send({"type": "webtransport.accept", "session_id": session_id})
    while True:
        event = await receive()
        if event["type"] == "webtransport.stream.receive":
            if stream_received is not None:
                stream_received.set()
            await send(
                {
                    "type": "webtransport.stream.send",
                    "session_id": session_id,
                    "stream_id": event["stream_id"],
                    "data": b"echo:" + event["data"],
                    "more": False,
                }
            )
            if stream_sent is not None:
                stream_sent.set()
            return
        if event["type"] in {"webtransport.close", "webtransport.disconnect"}:
            return


async def _wt_multi_lane_echo_app(scope, receive, send) -> None:
    assert scope["type"] == "webtransport"
    connect = await receive()
    assert connect["type"] == "webtransport.connect"
    session_id = connect["session_id"]
    assert scope["session_id"] == session_id
    assert scope["ext"]["webtransport"]["session_id"] == session_id
    await send({"type": "webtransport.accept", "session_id": session_id})
    while True:
        event = await receive()
        if event["type"] == "webtransport.stream.receive":
            if event.get("stream_direction") == "client_to_server":
                continue
            await send(
                {
                    "type": "webtransport.stream.send",
                    "session_id": session_id,
                    "stream_id": event["stream_id"],
                    "data": b"echo:" + event["data"],
                    "more": False,
                }
            )
        elif event["type"] == "webtransport.datagram.receive":
            await send(
                {
                    "type": "webtransport.datagram.send",
                    "session_id": session_id,
                    "datagram_id": event["datagram_id"],
                    "data": b"dg:" + event["data"],
                }
            )
        elif event["type"] in {"webtransport.close", "webtransport.disconnect"}:
            return


def _trace_events(trace: list[dict[str, object]]) -> set[str]:
    return {str(row["event"]) for row in trace}


def _trace_session_ids(trace: list[dict[str, object]]) -> set[str]:
    return {str(row["session_id"]) for row in trace if row.get("session_id")}


def _trace_rows_by_session(
    trace: list[dict[str, object]],
    *,
    event: str | None = None,
) -> dict[str, list[dict[str, object]]]:
    rows: dict[str, list[dict[str, object]]] = {}
    for row in trace:
        session_id = row.get("session_id")
        if not session_id:
            continue
        if event is not None and row.get("event") != event:
            continue
        rows.setdefault(str(session_id), []).append(row)
    return rows


def _trace_rows_for_session(
    trace: list[dict[str, object]],
    session_id: str,
) -> list[dict[str, object]]:
    return [row for row in trace if row.get("session_id") == session_id]


def _assert_session_lifecycle_trace(
    testcase: unittest.TestCase,
    trace: list[dict[str, object]],
    session_id: str,
    *,
    require_close: bool = True,
) -> None:
    session_rows = _trace_rows_for_session(trace, session_id)
    events = {str(row.get("event")) for row in session_rows}
    for expected in {
        "webtransport.connect.start",
        "webtransport.connect.response",
        "webtransport.stream.dispatch",
        "webtransport.stream.send",
        "webtransport.datagram.dispatch",
        "webtransport.datagram.send",
    }:
        testcase.assertIn(expected, events, session_rows)
    if require_close:
        testcase.assertIn("webtransport.session.cleanup", events, session_rows)


def _assert_transport_boundary_trace(testcase: unittest.TestCase, trace: list[dict[str, object]]) -> None:
    events = _trace_events(trace)
    for expected in {
        "quic.packet.receive",
        "quic.session.create",
        "quic.handshake.complete",
        "webtransport.connect.start",
        "webtransport.connect.response",
        "webtransport.stream.dispatch",
        "webtransport.datagram.dispatch",
    }:
        testcase.assertIn(expected, events)


def _assert_no_bad_trace_events(testcase: unittest.TestCase, trace: list[dict[str, object]]) -> None:
    bad = [
        row for row in trace
        if str(row.get("event", "")).endswith((".orphan", ".send.drop"))
        or row.get("event") == "quic.packet.decode_error"
        or "owner_mismatch" in str(row.get("event", ""))
    ]
    testcase.assertEqual(bad, [])


async def _start_wt_server(app=_wt_multi_lane_echo_app):
    cert_pem, key_pem = generate_self_signed_certificate("server.example")
    tmpdir = tempfile.TemporaryDirectory()
    certfile = Path(tmpdir.name) / "server-cert.pem"
    keyfile = Path(tmpdir.name) / "server-key.pem"
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
    )
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].transport.get_extra_info("sockname")[1]
    return server, port, cert_pem, tmpdir


