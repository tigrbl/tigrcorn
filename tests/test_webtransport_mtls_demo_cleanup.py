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
    SETTING_H3_DATAGRAM,
    SETTING_WT_ENABLED,
    STREAM_TYPE_CONTROL,
    encode_frame,
    encode_settings,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters, generate_self_signed_certificate
from tigrcorn.utils.bytes import encode_quic_varint


class WebTransportMtlsDemoCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_close_aborts_pending_webtransport_app_task(self) -> None:
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
            client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b"wtclose1")
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

                for _ in range(12):
                    data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                    response_state = None
                    for event in client.receive_datagram(data):
                        if event.kind == "stream":
                            candidate = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                            if event.stream_id == 0 and candidate is not None:
                                response_state = candidate
                    if response_state is not None and response_state.received_initial_headers:
                        self.assertIn((b":status", b"200"), response_state.headers)
                        break
                else:
                    self.fail("WebTransport CONNECT response was not received")

                pending_before_close = [
                    task
                    for task in asyncio.all_tasks()
                    if task is not asyncio.current_task()
                    and task.get_name().startswith("tigrcorn-h3-webtransport-")
                    and not task.done()
                ]
                self.assertTrue(pending_before_close)

                await server.close()
                await asyncio.sleep(0)

                pending_after_close = [
                    task
                    for task in asyncio.all_tasks()
                    if task is not asyncio.current_task()
                    and task.get_name().startswith("tigrcorn-h3-webtransport-")
                    and not task.done()
                ]
                self.assertEqual(pending_after_close, [])
            finally:
                sock.close()
                await server.close()
