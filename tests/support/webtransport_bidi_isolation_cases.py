from __future__ import annotations

import asyncio
import socket
import tempfile
from pathlib import Path

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
from tests.fixtures_third_party.wt_stream_client import probe_wt_stream
from tests.support.webtransport_bidi import (
    _assert_no_bad_trace_events,
    _assert_session_lifecycle_trace,
    _assert_transport_boundary_trace,
    _start_wt_server,
    _trace_events,
    _trace_rows_by_session,
    _trace_session_ids,
    _wt_child_stream_echo_app,
)


class WebTransportBidiIsolationCases:
    async def test_live_webtransport_concurrent_sessions_are_isolated(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            first, second = await asyncio.gather(
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"conc0001",
                    child_payloads=(b"left-a", b"left-b"),
                    datagram_payload=b"left-dg",
                    send_unidi=True,
                ),
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"conc0002",
                    child_payloads=(b"right-a", b"right-b"),
                    datagram_payload=b"right-dg",
                    send_unidi=True,
                ),
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(first.stream_bodies[4], b"echo:left-a")
        self.assertEqual(first.stream_bodies[8], b"echo:left-b")
        self.assertEqual(first.datagram_body, b"dg:left-dg")
        self.assertEqual(second.stream_bodies[4], b"echo:right-a")
        self.assertEqual(second.stream_bodies[8], b"echo:right-b")
        self.assertEqual(second.datagram_body, b"dg:right-dg")
        self.assertGreaterEqual(len(_trace_session_ids(trace)), 2)
        stream_dispatches = [row for row in trace if row["event"] == "webtransport.stream.dispatch"]
        self.assertGreaterEqual(len(stream_dispatches), 6)
        for row in stream_dispatches:
            self.assertIn("session_id", row)
            self.assertIn("owner_stream_id", row)
        for rows in _trace_rows_by_session(trace, event="webtransport.stream.dispatch").values():
            directions = {row.get("stream_direction") for row in rows}
            self.assertIn("bidi", directions)
            self.assertIn("client_to_server", directions)
        _assert_no_bad_trace_events(self, trace)

    async def test_live_webtransport_concurrent_sessions_multi_lane_burst_isolated(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            first, second = await asyncio.gather(
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"brst0001",
                    payload=b"left-unidi",
                    child_payloads=(b"left-a", b"left-b"),
                    datagram_payload=b"left-dg",
                    send_unidi=True,
                    burst_child_streams=True,
                ),
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"brst0002",
                    payload=b"right-unidi",
                    child_payloads=(b"right-a", b"right-b"),
                    datagram_payload=b"right-dg",
                    send_unidi=True,
                    burst_child_streams=True,
                ),
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(first.stream_bodies[4], b"echo:left-a")
        self.assertEqual(first.stream_bodies[8], b"echo:left-b")
        self.assertEqual(first.datagram_body, b"dg:left-dg")
        self.assertEqual(second.stream_bodies[4], b"echo:right-a")
        self.assertEqual(second.stream_bodies[8], b"echo:right-b")
        self.assertEqual(second.datagram_body, b"dg:right-dg")

        session_ids = _trace_session_ids(trace)
        self.assertGreaterEqual(len(session_ids), 2)
        _assert_transport_boundary_trace(self, trace)
        self.assertGreaterEqual(
            sum(1 for row in trace if row.get("event") == "quic.handshake.complete"),
            len(session_ids),
        )
        self.assertGreaterEqual(
            sum(1 for row in trace if row.get("event") == "webtransport.connect.response"),
            len(session_ids),
        )
        stream_dispatches = _trace_rows_by_session(trace, event="webtransport.stream.dispatch")
        datagram_dispatches = _trace_rows_by_session(trace, event="webtransport.datagram.dispatch")
        for session_id in session_ids:
            _assert_session_lifecycle_trace(self, trace, session_id)
            rows = stream_dispatches.get(session_id, [])
            self.assertGreaterEqual(
                sum(1 for row in rows if row.get("stream_direction") == "bidi"),
                2,
            )
            self.assertGreaterEqual(
                sum(1 for row in rows if row.get("stream_direction") == "client_to_server"),
                1,
            )
            self.assertGreaterEqual(len(datagram_dispatches.get(session_id, [])), 1)
            owned_rows = [
                row for row in trace
                if row.get("event") in {
                    "webtransport.stream.dispatch",
                    "webtransport.stream.send",
                    "webtransport.datagram.dispatch",
                    "webtransport.datagram.send",
                }
                and row.get("session_id") == session_id
            ]
            self.assertTrue(owned_rows)
            self.assertEqual({row["session_id"] for row in owned_rows}, {session_id})
        _assert_no_bad_trace_events(self, trace)

    async def test_webtransport_trace_contains_lifecycle_events_per_session(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"life0001",
                child_payloads=(b"trace-a", b"trace-b"),
                datagram_payload=b"trace-dg",
                send_unidi=True,
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        events = _trace_events(trace)
        for expected in {
            "quic.packet.receive",
            "quic.session.create",
            "quic.handshake.complete",
            "webtransport.connect.start",
            "webtransport.connect.response",
            "webtransport.stream.dispatch",
            "webtransport.stream.send",
            "webtransport.datagram.dispatch",
            "webtransport.datagram.send",
            "quic.connection.close.receive",
            "quic.session.close",
            "webtransport.session.cleanup",
        }:
            self.assertIn(expected, events)
        self.assertEqual(len(_trace_session_ids([row for row in trace if row.get("session_id")])), 1)

    async def test_webtransport_stream_ids_are_session_scoped(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            first, second = await asyncio.gather(
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"strm0001",
                    child_payloads=(b"s1-a", b"s1-b"),
                    datagram_payload=b"s1-dg",
                ),
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"strm0002",
                    child_payloads=(b"s2-a", b"s2-b"),
                    datagram_payload=b"s2-dg",
                ),
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(first.stream_bodies[4], b"echo:s1-a")
        self.assertEqual(second.stream_bodies[4], b"echo:s2-a")
        dispatches_for_stream_4 = [row for row in trace if row["event"] == "webtransport.stream.dispatch" and row.get("stream_id") == 4]
        self.assertGreaterEqual(len({row["session_id"] for row in dispatches_for_stream_4}), 2)

    async def test_webtransport_datagrams_are_session_scoped(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            first, second = await asyncio.gather(
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"dgrm0001",
                    child_payloads=(b"d1-a", b"d1-b"),
                    datagram_payload=b"d1",
                ),
                probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=b"dgrm0002",
                    child_payloads=(b"d2-a", b"d2-b"),
                    datagram_payload=b"d2",
                ),
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(first.datagram_body, b"dg:d1")
        self.assertEqual(second.datagram_body, b"dg:d2")
        dispatches = [row for row in trace if row["event"] == "webtransport.datagram.dispatch"]
        self.assertGreaterEqual(len({row["session_id"] for row in dispatches}), 2)
        _assert_no_bad_trace_events(self, trace)

    async def test_webtransport_unidi_and_bidi_streams_are_distinguished(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"lane0001",
                child_payloads=(b"bidi-a", b"bidi-b"),
                datagram_payload=b"lane-dg",
                send_unidi=True,
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        directions = {row.get("stream_direction") for row in trace if row["event"] == "webtransport.stream.dispatch"}
        self.assertIn("bidi", directions)
        self.assertIn("client_to_server", directions)

