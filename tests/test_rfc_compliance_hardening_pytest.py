import asyncio
import socket

from cryptography.hazmat.primitives import serialization

import pytest
from tigrcorn.config.load import build_config
from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.websocket.frames import OP_TEXT, parse_frame_bytes, serialize_frame
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.security.tls13.extensions import (
    ExtensionType,
    GROUP_SECP256R1,
    SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES,
    extension_dict,
)
from tigrcorn.security.tls13.handshake import QuicTransportError, _generate_key_share
from tigrcorn.security.tls13.messages import ClientHello, decode_handshake_message
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters, generate_self_signed_certificate


async def _start_http2_server(app):
    config = build_config(host='127.0.0.1', port=0, lifespan='off', http_versions=['2'])
    server = TigrCornServer(app, config)
    await server.start()
    port = server._listeners[0].server.sockets[0].getsockname()[1]
    return server, port


async def _start_http3_server(app):
    config = build_config(
        transport='udp',
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['3'],
        protocols=['http3'],
        quic_secret=b'shared',
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info('sockname')[1]
    return server, port


def test_client_hello_omits_legacy_session_id_and_offers_certificate_signature_algorithms():
    client = QuicTlsHandshakeDriver(is_client=True)
    client_hello_bytes = client.initiate()
    message, consumed = decode_handshake_message(client_hello_bytes, 0)
    assert consumed == len(client_hello_bytes)
    assert isinstance(message, ClientHello)
    assert message.legacy_session_id == b''
    offered = extension_dict(message.extensions)
    assert tuple(
        int(item) for item in offered[ExtensionType.SIGNATURE_ALGORITHMS_CERT]
    ) == SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES


def test_server_rejects_non_empty_legacy_session_id_as_quic_protocol_violation():
    client = QuicTlsHandshakeDriver(is_client=True)
    server = QuicTlsHandshakeDriver(is_client=False)
    client_hello_bytes = client.initiate()
    message, _consumed = decode_handshake_message(client_hello_bytes, 0)
    assert isinstance(message, ClientHello)
    tampered = ClientHello(
        random=message.random,
        legacy_session_id=b'legacy-session-id',
        cipher_suites=message.cipher_suites,
        compression_methods=message.compression_methods,
        extensions=message.extensions,
        legacy_version=message.legacy_version,
    ).encode()
    with pytest.raises(QuicTransportError) as ctx:
        server.receive(tampered)
    assert ctx.value.quic_error_code == 0x0A


def test_handshake_supports_secp256r1_key_shares():
    cert_pem, key_pem = generate_self_signed_certificate('server.example')
    client = QuicTlsHandshakeDriver(
        is_client=True,
        server_name='server.example',
        trusted_certificates=[cert_pem],
        transport_parameters=TransportParameters(max_data=11111),
    )
    client._local_key_share_group = GROUP_SECP256R1
    client._local_key_share_private, client._local_key_share_public = _generate_key_share(GROUP_SECP256R1)
    server = QuicTlsHandshakeDriver(
        is_client=False,
        server_name='server.example',
        certificate_pem=cert_pem,
        private_key_pem=key_pem,
        transport_parameters=TransportParameters(max_data=22222),
    )
    client_hello = client.initiate()
    server_flight = server.receive(client_hello)
    client_finished = client.receive(server_flight)
    server.receive(client_finished)
    assert client.complete
    assert server.complete
    assert client._local_key_share_group == GROUP_SECP256R1
    assert server._local_key_share_group == GROUP_SECP256R1
    assert client.peer_transport_parameters.max_data == 22222


@pytest.mark.asyncio
async def test_http2_websocket_denial_streaming():
    async def app(scope, receive, send):
        assert scope['type'] == 'websocket'
        connect = await receive()
        assert connect['type'] == 'websocket.connect'
        await send({'type': 'websocket.http.response.start', 'status': 401, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'websocket.http.response.body', 'body': b'part1-', 'more_body': True})
        await send({'type': 'websocket.http.response.body', 'body': b'part2', 'more_body': False})

    server, port = await _start_http2_server(app)
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        frame_writer = FrameWriter()
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        header_block = encode_header_block([
            (b':method', b'CONNECT'),
            (b':protocol', b'websocket'),
            (b':scheme', b'http'),
            (b':path', b'/chat'),
            (b':authority', b'example'),
            (b'sec-websocket-version', b'13'),
        ])
        writer.write(frame_writer.headers(1, header_block, end_stream=False))
        await writer.drain()

        buf = FrameBuffer()
        response_headers = []
        body = bytearray()
        end_stream = False
        while not end_stream:
            data = await asyncio.wait_for(reader.read(65535), 2.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    if frame.payload:
                        decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS:
                    response_headers.extend(decode_header_block(frame.payload))
                    if frame.flags & 0x1:
                        end_stream = True
                elif frame.frame_type == FRAME_DATA:
                    body.extend(frame.payload)
                    if frame.flags & 0x1:
                        end_stream = True
            if response_headers and end_stream:
                break

        assert (b':status', b'401') in response_headers
        assert (b'content-type', b'text/plain') in response_headers
        assert bytes(body) == b'part1-part2'
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http2_websocket_buffers_client_frames_until_accept():
    async def app(scope, receive, send):
        assert scope['type'] == 'websocket'
        connect = await receive()
        assert connect['type'] == 'websocket.connect'
        await send({'type': 'websocket.accept'})
        event = await receive()
        assert event['type'] == 'websocket.receive'
        assert event['text'] == 'early-h2-text'
        await send({'type': 'websocket.send', 'text': event['text']})

    server, port = await _start_http2_server(app)
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        frame_writer = FrameWriter()
        header_block = encode_header_block([
            (b':method', b'CONNECT'),
            (b':protocol', b'websocket'),
            (b':scheme', b'http'),
            (b':path', b'/chat'),
            (b':authority', b'example'),
            (b'sec-websocket-version', b'13'),
        ])
        early_frame = serialize_frame(OP_TEXT, b'early-h2-text', mask=True, mask_key=b'')
        writer.write(H2_PREFACE + serialize_settings({}) + frame_writer.headers(1, header_block, end_stream=False) + frame_writer.data(1, early_frame, end_stream=False))
        await writer.drain()

        buf = FrameBuffer()
        response_headers = []
        response_chunks = []
        while True:
            data = await asyncio.wait_for(reader.read(65535), 2.0)
            assert data
            buf.feed(data)
            for frame in buf.pop_all():
                if frame.frame_type == FRAME_SETTINGS:
                    if frame.payload:
                        decode_settings(frame.payload)
                elif frame.frame_type == FRAME_HEADERS:
                    response_headers.extend(decode_header_block(frame.payload))
                elif frame.frame_type == FRAME_DATA:
                    response_chunks.append(frame.payload)
            if response_headers and response_chunks:
                break

        assert response_headers[0] == (b':status', b'200')
        echoed = parse_frame_bytes(response_chunks[0], expect_masked=False)
        assert echoed.opcode == OP_TEXT
        assert echoed.payload.decode('utf-8') == 'early-h2-text'
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http3_websocket_denial_streaming():
    async def app(scope, receive, send):
        assert scope['type'] == 'websocket'
        connect = await receive()
        assert connect['type'] == 'websocket.connect'
        await send({'type': 'websocket.http.response.start', 'status': 401, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'websocket.http.response.body', 'body': b'part1-', 'more_body': True})
        await send({'type': 'websocket.http.response.body', 'body': b'part2', 'more_body': False})

    server, port = await _start_http3_server(app)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli-deny')
    core = HTTP3ConnectionCore()
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ('127.0.0.1', port))
        for _ in range(4):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                break

        payload = core.get_request(0).encode_request(
            [
                (b':method', b'CONNECT'),
                (b':protocol', b'websocket'),
                (b':scheme', b'https'),
                (b':path', b'/chat'),
                (b':authority', b'example'),
                (b'sec-websocket-version', b'13'),
            ],
            b'',
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
        assert (b':status', b'401') in response_state.headers
        assert (b'content-type', b'text/plain') in response_state.headers
        assert response_state.body == b'part1-part2'
    finally:
        sock.close()
        await server.close()
