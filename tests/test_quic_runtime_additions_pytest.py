import asyncio

from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.transports.udp.packet import UDPPacket

import pytest



def test_connection_id_issue_and_retire_roundtrip():
    left = QuicConnection(is_client=False, secret=b'shared', local_cid=b'servcid1', remote_cid=b'clicid01')
    right = QuicConnection(is_client=True, secret=b'shared', local_cid=b'clicid01', remote_cid=b'servcid1')
    sequence, cid, token, raw = left.issue_connection_id()
    events = right.receive_datagram(raw)
    assert any(event.kind == 'new_connection_id' for event in events)
    assert sequence in right.peer_connection_ids
    retire = right.retire_connection_id(sequence)
    left.receive_datagram(retire)
    assert sequence not in left.issued_connection_ids
def test_handshake_driver_integrates_with_connection_crypto_frames():
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
    server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
    client.configure_handshake(QuicTlsHandshakeDriver(is_client=True, server_name='server.example', trusted_certificates=[cert_pem]))
    server.configure_handshake(QuicTlsHandshakeDriver(is_client=False, server_name='server.example', certificate_pem=cert_pem, private_key_pem=key_pem))
    initial = client.start_handshake()
    server_events = server.receive_datagram(initial)
    assert any(event.kind == 'crypto' for event in server_events)
    server_outbound = server.take_handshake_datagrams()
    assert server_outbound
    client_events = []
    for raw in server_outbound:
        client_events.extend(client.receive_datagram(raw))
    assert any(event.kind == 'handshake_complete' for event in client_events)
    client_outbound = client.take_handshake_datagrams()
    assert client_outbound
    server_events = []
    for raw in client_outbound:
        server_events.extend(server.receive_datagram(raw))
    assert any(event.kind == 'handshake_complete' for event in server_events)
    assert client.address_validated
    assert server.address_validated

async def test_http3_runtime_applies_anti_amplification_limit():
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
        def __init__():
            self.sent = []
            self.local_addr = ('127.0.0.1', 4433)
        def send(data, addr):
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
    assert sum(len(raw) for raw, _ in endpoint.sent) <= session.bytes_received * 3