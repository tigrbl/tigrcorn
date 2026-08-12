import asyncio
import unittest

from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.packets import QuicRetryPacket, decode_packet
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.transports.udp.packet import UDPPacket


class QuicRuntimeAdditionsTests(unittest.TestCase):
    def test_connection_id_issue_and_retire_roundtrip(self):
        left = QuicConnection(is_client=False, secret=b'shared', local_cid=b'servcid1', remote_cid=b'clicid01')
        right = QuicConnection(is_client=True, secret=b'shared', local_cid=b'clicid01', remote_cid=b'servcid1')
        sequence, cid, token, raw = left.issue_connection_id()
        events = right.receive_datagram(raw)
        self.assertTrue(any(event.kind == 'new_connection_id' for event in events))
        self.assertIn(sequence, right.peer_connection_ids)
        retire = right.retire_connection_id(sequence)
        left.receive_datagram(retire)
        self.assertNotIn(sequence, left.issued_connection_ids)

    def test_handshake_driver_integrates_with_connection_crypto_frames(self):
        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        client.configure_handshake(QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem]))
        server.configure_handshake(QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem))
        initial = client.start_handshake()
        server_events = server.receive_datagram(initial)
        self.assertTrue(any(event.kind == 'crypto' for event in server_events))
        server_outbound = server.take_handshake_datagrams()
        self.assertTrue(server_outbound)
        client_events = []
        for raw in server_outbound:
            client_events.extend(client.receive_datagram(raw))
        self.assertTrue(any(event.kind == 'handshake_complete' for event in client_events))
        client_outbound = client.take_handshake_datagrams()
        self.assertTrue(client_outbound)
        server_events = []
        for raw in client_outbound:
            server_events.extend(server.receive_datagram(raw))
        self.assertTrue(any(event.kind == 'handshake_complete' for event in server_events))
        self.assertTrue(client.address_validated)
        self.assertTrue(server.address_validated)


class QuicAmplificationRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_established_connection_packet_bypasses_busy_registry(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(
                kind='udp', host='127.0.0.1', port=1, protocols=['http3'],
                quic_secret=b'shared', quic_require_retry=True,
            ),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)

            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        client = QuicConnection(
            is_client=True, secret=b'shared',
            local_cid=b'client01', remote_cid=b'server01',
        )
        client_addr = ('127.0.0.1', 50000)
        await handler.handle_packet(
            UDPPacket(data=client.build_initial(), addr=client_addr),
            endpoint,
        )
        retry_datagram = next(raw for raw, addr in endpoint.sent if addr == client_addr)
        client.receive_datagram(retry_datagram)

        await handler._lock.acquire()
        try:
            await asyncio.wait_for(
                handler.handle_packet(
                    UDPPacket(data=client.build_initial(), addr=client_addr),
                    endpoint,
                ),
                timeout=0.2,
            )
        finally:
            handler._lock.release()

    async def test_busy_connection_does_not_block_new_retry_handshake(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(
                kind='udp', host='127.0.0.1', port=1, protocols=['http3'],
                quic_secret=b'shared', quic_require_retry=True,
            ),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)

            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        presenter = QuicConnection(
            is_client=True, secret=b'shared',
            local_cid=b'present1', remote_cid=b'server01',
        )
        presenter_addr = ('127.0.0.1', 50000)
        await handler.handle_packet(
            UDPPacket(data=presenter.build_initial(), addr=presenter_addr),
            endpoint,
        )
        retry_datagram = next(raw for raw, addr in endpoint.sent if addr == presenter_addr)
        presenter.receive_datagram(retry_datagram)
        presenter_session = handler.sessions[presenter_addr]

        await presenter_session.lock.acquire()
        blocked_presenter_packet = asyncio.create_task(
            handler.handle_packet(
                UDPPacket(data=presenter.build_initial(), addr=presenter_addr),
                endpoint,
            )
        )
        await asyncio.sleep(0)

        audience_addr = ('127.0.0.1', 50001)
        audience = QuicConnection(
            is_client=True, secret=b'shared',
            local_cid=b'audienc1', remote_cid=b'server02',
        )
        await asyncio.wait_for(
            handler.handle_packet(
                UDPPacket(data=audience.build_initial(), addr=audience_addr),
                endpoint,
            ),
            timeout=0.2,
        )
        self.assertTrue(any(addr == audience_addr for _raw, addr in endpoint.sent))

        presenter_session.lock.release()
        await blocked_presenter_packet

    async def test_http3_retry_survives_client_udp_port_rebinding(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(
                kind='udp', host='127.0.0.1', port=1, protocols=['http3'],
                quic_secret=b'shared', quic_require_retry=True,
            ),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)

            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        client = QuicConnection(
            is_client=True, secret=b'shared',
            local_cid=b'cli1cli1', remote_cid=b'srv1srv1',
        )
        await handler.handle_packet(
            UDPPacket(data=client.build_initial(), addr=('127.0.0.1', 50000)),
            endpoint,
        )
        retry_datagram = next(
            raw for raw, _addr in endpoint.sent
            if raw[0] & 0x80 and isinstance(decode_packet(raw), QuicRetryPacket)
        )
        client.receive_datagram(retry_datagram)
        retry_cid = client.remote_cid
        endpoint.sent.clear()

        await handler.handle_packet(
            UDPPacket(data=client.build_initial(), addr=('127.0.0.1', 50001)),
            endpoint,
        )

        self.assertEqual(len(handler.sessions), 1)
        session = next(iter(handler.sessions.values()))
        self.assertEqual(session.addr, ('127.0.0.1', 50001))
        self.assertTrue(session.quic.address_validated)
        self.assertIs(handler.sessions_by_local_cid[retry_cid], session)

    async def test_http3_runtime_applies_anti_amplification_limit(self):
        async def app(scope, receive, send):
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'x' * 12000, 'more_body': False})

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3'], quic_secret=b'shared'),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)
            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1')
        await handler.handle_packet(UDPPacket(data=client.build_initial(), addr=('127.0.0.1', 50000)), endpoint)
        core = HTTP3ConnectionCore()
        for raw, _addr in endpoint.sent:
            for event in client.receive_datagram(raw):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        endpoint.sent.clear()
        request_payload = core.get_request(0).encode_request([(b':method', b'POST'), (b':path', b'/big'), (b':scheme', b'https')], b'hi')
        await handler.handle_packet(UDPPacket(data=client.send_stream_data(0, request_payload, fin=True), addr=('127.0.0.1', 50000)), endpoint)
        session = next(iter(handler.sessions.values()))
        self.assertLessEqual(sum(len(raw) for raw, _ in endpoint.sent), session.bytes_received * 3)
