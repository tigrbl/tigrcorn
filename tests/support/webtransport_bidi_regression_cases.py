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


class WebTransportBidiRegressionCases:
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
                    transport_parameters=TransportParameters(
                        max_datagram_frame_size=65536,
                        reset_stream_at=True,
                    ),
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
