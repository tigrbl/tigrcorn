import asyncio
import os
import socket
import tempfile

from tigrcorn.config.load import build_config
from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.websocket.frames import decode_close_payload, encode_frame, parse_frame_bytes
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate


import pytest
def _frame_wire_length(data: bytes) -> int:
    if len(data) < 2:
        raise AssertionError('websocket frame is truncated')
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7F
    pos = 2
    if length == 126:
        if len(data) < pos + 2:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
    elif length == 127:
        if len(data) < pos + 8:
            raise AssertionError('websocket frame is truncated')
        length = int.from_bytes(data[pos:pos + 8], 'big')
        pos += 8
    if masked:
        pos += 4
    total = pos + length
    if len(data) < total:
        raise AssertionError('websocket frame is truncated')
    return total



def test_client_initial_datagrams_meet_the_rfc_minimum_size():
    client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b'cli1cli1')
    assert len(client.build_initial()) >= 1200
    cert_pem, _key_pem = generate_self_signed_certificate('server.example')
    client.configure_handshake(
        QuicTlsHandshakeDriver(
            is_client=True,
            server_name='server.example',
            trusted_certificates=[cert_pem],
        )
    )
    assert len(client.start_handshake()) >= 1200

async def test_http3_roundtrip_works_with_public_udp_tls_config():
    async def app(scope, receive, send):
        assert scope['type'] == 'http'
        assert scope['http_version'] == '3'
        assert scope['path'] == '/h3'
        event = await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'echo:' + event['body'], 'more_body': False})

    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = os.path.join(tmpdir, 'server-cert.pem')
        keyfile = os.path.join(tmpdir, 'server-key.pem')
        with open(certfile, 'wb') as handle:
            handle.write(cert_pem)
        with open(keyfile, 'wb') as handle:
            handle.write(key_pem)

        config = build_config(
            transport='udp',
            host='127.0.0.1',
            port=0,
            lifespan='off',
            http_versions=['3'],
            protocols=['http3'],
            ssl_certfile=certfile,
            ssl_keyfile=keyfile,
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info('sockname')[1]

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b'cli1cli1')
        client.configure_handshake(
            QuicTlsHandshakeDriver(
                is_client=True,
                server_name='server.example',
                trusted_certificates=[cert_pem],
            )
        )
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.start_handshake(), ('127.0.0.1', port))
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                for datagram in client.take_handshake_datagrams():
                    sock.sendto(datagram, ('127.0.0.1', port))
                if client.handshake_driver is not None and client.handshake_driver.complete:
                    break
            assert client.handshake_driver is not None
            assert client.handshake_driver is not None
            assert client.handshake_driver.complete
            payload = core.get_request(0).encode_request(
                [(b':method', b'POST'), (b':path', b'/h3'), (b':scheme', b'https')],
                b'hello',
            )
            sock.sendto(client.send_stream_data(0, payload, fin=True), ('127.0.0.1', port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None:
                    break

            assert response_state is not None
            assert response_state is not None
            assert (b':status' in b'200'), response_state.headers
            assert response_state.body == b'echo:hello'
        finally:
            sock.close()
            await server.close()

async def test_http3_roundtrip_supports_quic_client_auth():
    async def app(scope, receive, send):
        assert scope['type'] == 'http'
        assert scope['http_version'] == '3'
        event = await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'mtls:' + event['body'], 'more_body': False})

    server_cert, server_key = generate_self_signed_certificate('server.example', purpose='server')
    client_cert, client_key = generate_self_signed_certificate('client.example', purpose='client')
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = os.path.join(tmpdir, 'server-cert.pem')
        keyfile = os.path.join(tmpdir, 'server-key.pem')
        cafile = os.path.join(tmpdir, 'client-ca.pem')
        with open(certfile, 'wb') as handle:
            handle.write(server_cert)
        with open(keyfile, 'wb') as handle:
            handle.write(server_key)
        with open(cafile, 'wb') as handle:
            handle.write(client_cert)

        config = build_config(
            transport='udp',
            host='127.0.0.1',
            port=0,
            lifespan='off',
            http_versions=['3'],
            protocols=['http3'],
            ssl_certfile=certfile,
            ssl_keyfile=keyfile,
            ssl_ca_certs=cafile,
            ssl_require_client_cert=True,
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info('sockname')[1]

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b'cli3cli3')
        client.configure_handshake(
            QuicTlsHandshakeDriver(
                is_client=True,
                server_name='server.example',
                trusted_certificates=[server_cert],
                certificate_pem=client_cert,
                private_key_pem=client_key,
            )
        )
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.start_handshake(), ('127.0.0.1', port))
            for _ in range(12):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                for datagram in client.take_handshake_datagrams():
                    sock.sendto(datagram, ('127.0.0.1', port))
                if client.handshake_driver is not None and client.handshake_driver.complete:
                    break
            assert client.handshake_driver is not None
            assert client.handshake_driver is not None
            assert client.handshake_driver.complete
            payload = core.get_request(0).encode_request(
                [(b':method', b'POST'), (b':path', b'/mtls'), (b':scheme', b'https')],
                b'hello',
            )
            sock.sendto(client.send_stream_data(0, payload, fin=True), ('127.0.0.1', port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None:
                    break

            assert response_state is not None
            assert response_state is not None
            assert (b':status' in b'200'), response_state.headers
            assert response_state.body == b'mtls:hello'
        finally:
            sock.close()
            await server.close()

async def test_http3_websocket_roundtrip_works_with_public_udp_tls_config():
    seen = {}

    async def app(scope, receive, send):
        assert scope['type'] == 'websocket'
        assert scope['http_version'] == '3'
        assert scope['path'] == '/chat'
        assert scope['scheme'] == 'wss'
        await receive()
        await send({'type': 'websocket.accept', 'subprotocol': 'chat', 'headers': []})
        event = await receive()
        seen['text'] = event['text']
        await send({'type': 'websocket.send', 'text': event['text']})
        await send({'type': 'websocket.close', 'code': 1000})

    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    with tempfile.TemporaryDirectory() as tmpdir:
        certfile = os.path.join(tmpdir, 'server-cert.pem')
        keyfile = os.path.join(tmpdir, 'server-key.pem')
        with open(certfile, 'wb') as handle:
            handle.write(cert_pem)
        with open(keyfile, 'wb') as handle:
            handle.write(key_pem)

        config = build_config(
            transport='udp',
            host='127.0.0.1',
            port=0,
            lifespan='off',
            http_versions=['3'],
            protocols=['http3'],
            ssl_certfile=certfile,
            ssl_keyfile=keyfile,
        )
        server = TigrCornServer(app, config)
        await server.start()
        port = server._listeners[0].transport.get_extra_info('sockname')[1]

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=b'cli2cli2')
        client.configure_handshake(
            QuicTlsHandshakeDriver(
                is_client=True,
                server_name='server.example',
                trusted_certificates=[cert_pem],
            )
        )
        core = HTTP3ConnectionCore()
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.start_handshake(), ('127.0.0.1', port))
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                for datagram in client.take_handshake_datagrams():
                    sock.sendto(datagram, ('127.0.0.1', port))
                if client.handshake_driver is not None and client.handshake_driver.complete:
                    break
            assert client.handshake_driver is not None
            assert client.handshake_driver is not None
            assert client.handshake_driver.complete
            payload = core.get_request(0).encode_request(
                [
                    (b':method', b'CONNECT'),
                    (b':protocol', b'websocket'),
                    (b':scheme', b'https'),
                    (b':path', b'/chat'),
                    (b':authority', b'server.example'),
                    (b'sec-websocket-version', b'13'),
                    (b'sec-websocket-protocol', b'chat'),
                ],
                encode_frame(0x1, b'hello-h3-tls', masked=True),
            )
            sock.sendto(client.send_stream_data(0, payload, fin=False), ('127.0.0.1', port))

            response_state = None
            for _ in range(10):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if response_state is not None and response_state.ended:
                    break

            assert response_state is not None
            assert response_state is not None
            assert (b':status' in b'200'), response_state.headers
            assert (b'sec-websocket-protocol' in b'chat'), response_state.headers
            assert seen['text'] == 'hello-h3-tls'
            first_len = _frame_wire_length(response_state.body)
            message_frame = parse_frame_bytes(response_state.body[:first_len], expect_masked=False)
            assert message_frame.payload.decode('utf-8') == 'hello-h3-tls'
            close_frame = parse_frame_bytes(response_state.body[first_len:], expect_masked=False)
            code, reason = decode_close_payload(close_frame.payload)
            assert code == 1000
            assert reason == ''
        finally:
            sock.close()
            await server.close()
