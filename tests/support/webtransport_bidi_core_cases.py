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
    SETTING_WT_ENABLED,
    SETTING_H3_DATAGRAM,
    STREAM_TYPE_CONTROL,
    encode_frame,
    encode_settings,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters, generate_self_signed_certificate
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


class WebTransportBidiCoreCases:
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
                    transport_parameters=TransportParameters(
                        max_datagram_frame_size=65536,
                        reset_stream_at=True,
                    ),
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
                            SETTING_WT_ENABLED: 1,
                        }
                    ),
                )
                sock.sendto(client.send_stream_data(control_stream_id, control_payload, fin=False), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                connect_payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport-h3"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
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

    async def test_live_webtransport_quic_h3_connect_transcript_proves_transport_boundary(self) -> None:
        server, port, cert_pem, tmpdir = await _start_wt_server()
        try:
            response = await probe_wt_stream(
                "127.0.0.1",
                port,
                trusted_certificates=[cert_pem],
                local_cid=b"proof001",
                child_payloads=(b"proof-a", b"proof-b"),
                datagram_payload=b"proof-dg",
                send_unidi=True,
            )
            await asyncio.sleep(0.05)
            trace = list(server._datagram_handlers[0].webtransport_trace)
        finally:
            await server.close()
            tmpdir.cleanup()

        self.assertTrue(response.handshake_complete)
        self.assertTrue(response.connect_response_received)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.stream_bodies[4], b"echo:proof-a")
        self.assertEqual(response.stream_bodies[8], b"echo:proof-b")
        self.assertEqual(response.datagram_body, b"dg:proof-dg")
        self.assertIn("stream", response.quic_events)
        self.assertIn("datagram", response.quic_events)
        self.assertEqual(response.remote_settings[SETTING_ENABLE_CONNECT_PROTOCOL], 1)
        self.assertEqual(response.remote_settings[SETTING_H3_DATAGRAM], 1)
        self.assertEqual(response.remote_settings[SETTING_WT_ENABLED], 1)

        _assert_transport_boundary_trace(self, trace)
        session_ids = _trace_session_ids(trace)
        self.assertEqual(len(session_ids), 1)
        session_id = next(iter(session_ids))
        _assert_session_lifecycle_trace(self, trace, session_id)
        _assert_no_bad_trace_events(self, trace)

