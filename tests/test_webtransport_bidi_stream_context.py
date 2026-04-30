from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
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
