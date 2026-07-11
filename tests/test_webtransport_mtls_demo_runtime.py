from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path

from examples.webtransport_mtls_demo.server import app
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
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint


class WebTransportMtlsDemoRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_webtransport_listener_completes_quic_tls_handshake(self) -> None:
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
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtlocal1")
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
            loop = asyncio.get_running_loop()
            try:
                sock.sendto(client.start_handshake(), ("127.0.0.1", port))
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    client.receive_datagram(data)
                    for datagram in client.take_handshake_datagrams():
                        sock.sendto(datagram, ("127.0.0.1", port))
                    if client.handshake_driver is not None and client.handshake_driver.complete:
                        break

                self.assertIsNotNone(client.handshake_driver)
                assert client.handshake_driver is not None
                self.assertTrue(client.handshake_driver.complete)
            finally:
                sock.close()
                await server.close()

    async def test_local_webtransport_listener_accepts_extended_connect(self) -> None:
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
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtconn01")
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
            loop_errors: list[BaseException] = []
            previous_exception_handler = loop.get_exception_handler()

            def capture_loop_exception(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
                exception = context.get("exception")
                if isinstance(exception, BaseException):
                    loop_errors.append(exception)

            loop.set_exception_handler(capture_loop_exception)
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

                payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport-h3"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
                    ]
                )
                sock.sendto(client.send_stream_data(0, payload, fin=False), ("127.0.0.1", port))

                response_state = None
                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None:
                                response_state = candidate
                    if response_state is not None and response_state.received_initial_headers:
                        break

                self.assertIn(SETTING_ENABLE_CONNECT_PROTOCOL, core.state.remote_settings)
                self.assertEqual(core.state.remote_settings.get(SETTING_H3_DATAGRAM), 1)
                self.assertEqual(core.state.remote_settings.get(SETTING_WT_ENABLED), 1)
                self.assertIsNotNone(response_state)
                assert response_state is not None
                self.assertIn((b":status", b"200"), response_state.headers)
                self.assertEqual(loop_errors, [])
            finally:
                loop.set_exception_handler(previous_exception_handler)
                sock.close()
                await server.close()

    async def test_connect_stream_fin_does_not_break_webtransport_datagrams(self) -> None:
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
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtfin001")
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
                settings = encode_frame(
                    FRAME_SETTINGS,
                    encode_settings(
                        {
                            SETTING_ENABLE_CONNECT_PROTOCOL: 1,
                            SETTING_H3_DATAGRAM: 1,
                            SETTING_WT_ENABLED: 1,
                        }
                    ),
                )
                control_payload = encode_quic_varint(STREAM_TYPE_CONTROL) + settings
                sock.sendto(client.send_stream_data(control_stream_id, control_payload, fin=False), ("127.0.0.1", port))
                await asyncio.sleep(0.05)

                payload = core.get_request(0).encode_request(
                    [
                        (b":method", b"CONNECT"),
                        (b":protocol", b"webtransport-h3"),
                        (b":scheme", b"https"),
                        (b":path", b"/wt"),
                        (b":authority", b"server.example"),
                        (b"origin", b"https://localhost:8088"),
                    ]
                )
                sock.sendto(client.send_stream_data(0, payload, fin=True), ("127.0.0.1", port))

                accepted_datagram = None
                response_state = None
                for _ in range(16):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None:
                                response_state = candidate
                        elif event.kind == "datagram":
                            quarter_stream_id, offset = decode_quic_varint(event.data, 0)
                            if quarter_stream_id == 0:
                                accepted_datagram = event.data[offset:]
                    if response_state is not None and response_state.received_initial_headers and accepted_datagram is not None:
                        break

                self.assertIsNotNone(response_state)
                assert response_state is not None
                self.assertIn((b":status", b"200"), response_state.headers)
                self.assertEqual(core.state.remote_settings.get(SETTING_H3_DATAGRAM), 1)
                self.assertIsNotNone(accepted_datagram)
                assert accepted_datagram is not None
                self.assertIn(b'"event": "accepted"', accepted_datagram)

                datagram_payload = encode_quic_varint(0) + b"client-ping"
                sock.sendto(client.send_datagram_frame(datagram_payload), ("127.0.0.1", port))

                echoed_datagram = None
                for _ in range(16):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    for event in client.receive_datagram(data):
                        if event.kind == "datagram":
                            quarter_stream_id, offset = decode_quic_varint(event.data, 0)
                            if quarter_stream_id == 0:
                                payload = event.data[offset:]
                                if payload.startswith(b"ack:client-ping"):
                                    echoed_datagram = payload
                                    break
                    if echoed_datagram is not None:
                        break

                self.assertEqual(echoed_datagram, b"ack:client-ping")
            finally:
                sock.close()
                await server.close()
