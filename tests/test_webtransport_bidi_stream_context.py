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


class WebTransportBidiStreamContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_sending_on_connect_stream_does_not_abort_active_session(self) -> None:
        stream_received = asyncio.Event()
        stream_sent = asyncio.Event()

        async def app(scope, receive, send):
            await _wt_child_stream_echo_app(scope, receive, send, stream_received=stream_received, stream_sent=stream_sent)

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
            )
            server = TigrCornServer(app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtstop01")
            client.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name="server.example",
                    trusted_certificates=[cert_pem],
                )
            )
            core = HTTP3ConnectionCore()
            loop = asyncio.get_running_loop()
            try:
                sock.sendto(client.start_handshake(), ("127.0.0.1", port))
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                    for datagram in client.take_handshake_datagrams():
                        sock.sendto(datagram, ("127.0.0.1", port))
                    if client.handshake_driver is not None and client.handshake_driver.complete:
                        break

                control_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
                control_payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(
                    FRAME_SETTINGS,
                    encode_settings(
                        {
                            SETTING_ENABLE_CONNECT_PROTOCOL: 1,
                            SETTING_H3_DATAGRAM: 1,
                            SETTING_ENABLE_WEBTRANSPORT: 1,
                        }
                    ),
                )
                sock.sendto(client.send_stream_data(control_stream_id, control_payload, fin=False), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                connect_payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ]
                )
                sock.sendto(client.send_stream_data(0, connect_payload, fin=False), ("127.0.0.1", port))

                response_ready = False
                for _ in range(16):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None and candidate.received_initial_headers:
                                response_ready = True
                    if response_ready:
                        break

                self.assertTrue(response_ready)

                sock.sendto(client.stop_sending(0, 0), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                observed_reset_stream = False
                try:
                    for _ in range(4):
                        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 0.2)
                        for event in client.receive_datagram(data):
                            if event.kind == "reset_stream" and event.stream_id == 0:
                                observed_reset_stream = True
                except TimeoutError:
                    pass

                self.assertFalse(observed_reset_stream)

                child_stream_id = 4
                child_payload = encode_quic_varint(0x41) + encode_quic_varint(0) + b"child-payload"
                sock.sendto(client.send_stream_data(child_stream_id, child_payload, fin=True), ("127.0.0.1", port))

                await asyncio.wait_for(stream_received.wait(), 1.0)
                await asyncio.wait_for(stream_sent.wait(), 1.0)
            finally:
                sock.close()
                await server.close()

    async def test_live_webtransport_two_sequential_sessions_roundtrip(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            first = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"seq00001",
                child_payloads=(b"a1", b"a2"),
                datagram_payload=b"adg",
                send_unidi=True,
            )
            await asyncio.sleep(0.05)
            second = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"seq00002",
                child_payloads=(b"b1", b"b2"),
                datagram_payload=b"bdg",
                send_unidi=True,
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(first.stream_bodies[4], b"echo:a1")
        self.assertEqual(first.stream_bodies[8], b"echo:a2")
        self.assertEqual(first.datagram_body, b"dg:adg")
        self.assertEqual(second.stream_bodies[4], b"echo:b1")
        self.assertEqual(second.stream_bodies[8], b"echo:b2")
        self.assertEqual(second.datagram_body, b"dg:bdg")
        self.assertGreaterEqual(len(_trace_session_ids(trace)), 2)
        self.assertGreaterEqual(sum(1 for row in trace if row["event"] == "quic.handshake.complete"), 2)
        self.assertGreaterEqual(sum(1 for row in trace if row["event"] == "webtransport.connect.response"), 2)
        self.assertIn("quic.connection.close.receive", _trace_events(trace))
        _assert_no_bad_trace_events(self, trace)

    async def test_live_webtransport_many_sequential_sessions_roundtrip(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            for index in range(5):
                response = await probe_wt_stream(
                    "127.0.0.1",
                    port,
                    trusted_certificates=[cert_pem],
                    local_cid=f"many{index:04d}".encode("ascii"),
                    child_payloads=(f"{index}-a".encode("ascii"), f"{index}-b".encode("ascii")),
                    datagram_payload=f"{index}-dg".encode("ascii"),
                    send_unidi=True,
                )
                self.assertEqual(response.stream_bodies[4], b"echo:" + f"{index}-a".encode("ascii"))
                self.assertEqual(response.stream_bodies[8], b"echo:" + f"{index}-b".encode("ascii"))
                self.assertEqual(response.datagram_body, b"dg:" + f"{index}-dg".encode("ascii"))
                await asyncio.sleep(0.02)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertGreaterEqual(len(_trace_session_ids(trace)), 5)
        self.assertGreaterEqual(sum(1 for row in trace if row["event"] == "webtransport.connect.response"), 5)
        _assert_no_bad_trace_events(self, trace)

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
        stream_dispatches = _trace_rows_by_session(trace, event="webtransport.stream.dispatch")
        datagram_dispatches = _trace_rows_by_session(trace, event="webtransport.datagram.dispatch")
        for session_id in session_ids:
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

    async def test_webtransport_partial_handshake_does_not_block_later_session(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            partial = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"part0001")
            partial.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name="server.example",
                    trusted_certificates=[cert_pem],
                )
            )
            sock.sendto(partial.start_handshake(), ("127.0.0.1", port))
            sock.setblocking(False)
            await asyncio.sleep(0.05)
            response = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"part0002",
                child_payloads=(b"valid-a", b"valid-b"),
                datagram_payload=b"valid-dg",
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            if sock.fileno() != -1:
                sock.close()
            await server.close()
            tmpdir.cleanup()

        self.assertEqual(response.stream_bodies[4], b"echo:valid-a")
        self.assertIn("quic.handshake.complete", _trace_events(trace))
        self.assertIn("webtransport.connect.response", _trace_events(trace))

    async def test_webtransport_second_session_post_initial_progresses(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"post0001",
                child_payloads=(b"first-a", b"first-b"),
                datagram_payload=b"first-dg",
            )
            await asyncio.sleep(0.05)
            await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"post0002",
                child_payloads=(b"second-a", b"second-b"),
                datagram_payload=b"second-dg",
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertGreaterEqual(sum(1 for row in trace if row["event"] == "quic.handshake.complete"), 2, trace)
        self.assertGreaterEqual(sum(1 for row in trace if row["event"] == "webtransport.connect.response"), 2, trace)

    async def test_active_webtransport_session_claims_child_bidi_stream_context(self) -> None:
        stream_received = asyncio.Event()
        stream_sent = asyncio.Event()

        async def app(scope, receive, send):
            await _wt_child_stream_echo_app(scope, receive, send, stream_received=stream_received, stream_sent=stream_sent)

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
            )
            server = TigrCornServer(app, config)
            await server.start()
            port = server._listeners[0].transport.get_extra_info("sockname")[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtbidi01")
            client.configure_handshake(
                QuicTlsHandshakeDriver(
                    is_client=True,
                    server_name="server.example",
                    trusted_certificates=[cert_pem],
                )
            )
            core = HTTP3ConnectionCore()
            loop = asyncio.get_running_loop()
            try:
                sock.sendto(client.start_handshake(), ("127.0.0.1", port))
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                    for datagram in client.take_handshake_datagrams():
                        sock.sendto(datagram, ("127.0.0.1", port))
                    if client.handshake_driver is not None and client.handshake_driver.complete:
                        break

                control_stream_id = client.streams.next_stream_id(client=True, unidirectional=True)
                control_payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(
                    FRAME_SETTINGS,
                    encode_settings(
                        {
                            SETTING_ENABLE_CONNECT_PROTOCOL: 1,
                            SETTING_H3_DATAGRAM: 1,
                            SETTING_ENABLE_WEBTRANSPORT: 1,
                        }
                    ),
                )
                sock.sendto(client.send_stream_data(control_stream_id, control_payload, fin=False), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                connect_payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ]
                )
                sock.sendto(client.send_stream_data(0, connect_payload, fin=False), ("127.0.0.1", port))

                response_ready = False
                for _ in range(16):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None and candidate.received_initial_headers:
                                response_ready = True
                    if response_ready:
                        break

                self.assertTrue(response_ready)

                child_stream_id = 4
                child_payload = encode_quic_varint(0x41) + encode_quic_varint(0) + b"child-payload"
                sock.sendto(client.send_stream_data(child_stream_id, child_payload, fin=True), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                handler = server._datagram_handlers[0]
                runtime_session = next(iter(handler.sessions.values()))

                try:
                    await asyncio.wait_for(stream_received.wait(), 1.0)
                    await asyncio.wait_for(stream_sent.wait(), 1.0)
                except TimeoutError as exc:
                    raise AssertionError(
                        "child WebTransport bidi stream was not dispatched to the app; "
                        f"owners={runtime_session.webtransport_stream_owners!r} "
                        f"streams={runtime_session.webtransport_streams!r}"
                    ) from exc

                child_data = bytearray()
                child_fin = False
                for _ in range(16):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream" and event.stream_id == child_stream_id:
                            child_data.extend(event.data)
                            child_fin = child_fin or event.fin
                    if child_data or child_fin:
                        break

                self.assertEqual(bytes(child_data), b"echo:child-payload")
                self.assertTrue(child_fin)
            finally:
                sock.close()
                await server.close()


if __name__ == "__main__":
    unittest.main()
