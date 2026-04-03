import asyncio
import socket

import pytest

from tigrcorn.config.load import build_config
from tigrcorn.protocols.http3 import (
    H3_FRAME_UNEXPECTED,
    H3_ID_ERROR,
    H3_MESSAGE_ERROR,
    H3_MISSING_SETTINGS,
    H3_SETTINGS_ERROR,
    HTTP3ConnectionCore,
    HTTP3ConnectionError,
    HTTP3StreamError,
    encode_field_section,
    encode_frame,
)
from tigrcorn.protocols.http3.codec import (
    FRAME_DATA,
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_PUSH_PROMISE,
    FRAME_SETTINGS,
    STREAM_TYPE_CONTROL,
)
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.utils.bytes import encode_quic_varint


async def _start_h3_server(app):
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


def test_request_stream_rejects_data_before_headers():
    core = HTTP3ConnectionCore(role='server')
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(0, encode_frame(FRAME_DATA, b'body'))
    assert ctx.value.error_code == H3_FRAME_UNEXPECTED


def test_request_stream_rejects_data_after_trailers():
    core = HTTP3ConnectionCore(role='server')
    payload = (
        encode_frame(
            FRAME_HEADERS,
            encode_field_section(
                [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https')]
            ),
        )
        + encode_frame(FRAME_HEADERS, encode_field_section([(b'checksum', b'ok')]))
        + encode_frame(FRAME_DATA, b'x')
    )
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(0, payload)
    assert ctx.value.error_code == H3_FRAME_UNEXPECTED


def test_request_stream_content_length_mismatch_is_stream_error():
    core = HTTP3ConnectionCore(role='server')
    payload = (
        encode_frame(
            FRAME_HEADERS,
            encode_field_section(
                [
                    (b':method', b'POST'),
                    (b':path', b'/upload'),
                    (b':scheme', b'https'),
                    (b'content-length', b'4'),
                ]
            ),
        )
        + encode_frame(FRAME_DATA, b'abc')
    )
    with pytest.raises(HTTP3StreamError) as ctx:
        core.receive_stream_data(0, payload, fin=True)
    assert ctx.value.error_code == H3_MESSAGE_ERROR


def test_unknown_frame_type_is_ignored_on_request_stream():
    core = HTTP3ConnectionCore(role='server')
    payload = (
        encode_frame(
            FRAME_HEADERS,
            encode_field_section(
                [
                    (b':method', b'POST'),
                    (b':path', b'/ok'),
                    (b':scheme', b'https'),
                    (b'content-length', b'1'),
                ]
            ),
        )
        + encode_frame(0x21, b'padding')
        + encode_frame(FRAME_DATA, b'a')
    )
    state = core.receive_stream_data(0, payload, fin=True)
    assert state.body == b'a'
    assert state.ready


def test_control_stream_requires_settings_first():
    core = HTTP3ConnectionCore(role='client')
    payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(
        FRAME_GOAWAY, encode_quic_varint(0)
    )
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(3, payload)
    assert ctx.value.error_code == H3_MISSING_SETTINGS


def test_reserved_settings_are_rejected():
    core = HTTP3ConnectionCore(role='client')
    reserved_payload = encode_quic_varint(0x02) + encode_quic_varint(1)
    payload = encode_quic_varint(STREAM_TYPE_CONTROL) + encode_frame(
        FRAME_SETTINGS, reserved_payload
    )
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(3, payload)
    assert ctx.value.error_code == H3_SETTINGS_ERROR


def test_push_promise_is_forbidden_on_server_request_stream():
    core = HTTP3ConnectionCore(role='server')
    promise_payload = encode_quic_varint(0) + encode_field_section(
        [(b':method', b'GET'), (b':path', b'/pushed')]
    )
    payload = (
        encode_frame(
            FRAME_HEADERS,
            encode_field_section(
                [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https')]
            ),
        )
        + encode_frame(FRAME_PUSH_PROMISE, promise_payload)
    )
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(0, payload)
    assert ctx.value.error_code == H3_FRAME_UNEXPECTED


def test_goaway_identifier_must_not_increase():
    core = HTTP3ConnectionCore(role='client')
    payload = (
        encode_quic_varint(STREAM_TYPE_CONTROL)
        + encode_frame(FRAME_SETTINGS, b'')
        + encode_frame(FRAME_GOAWAY, encode_quic_varint(16))
        + encode_frame(FRAME_GOAWAY, encode_quic_varint(20))
    )
    with pytest.raises(HTTP3ConnectionError) as ctx:
        core.receive_stream_data(3, payload)
    assert ctx.value.error_code == H3_ID_ERROR


@pytest.mark.asyncio
async def test_server_resets_stream_for_malformed_request():
    app_called = False

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True
        raise AssertionError('malformed request should not reach the app')

    server, port = await _start_h3_server(app)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
    loop = asyncio.get_running_loop()
    try:
        sock.sendto(client.build_initial(), ('127.0.0.1', port))
        for _ in range(2):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            client.receive_datagram(data)
        bad_request = (
            encode_frame(
                FRAME_HEADERS,
                encode_field_section(
                    [
                        (b':method', b'POST'),
                        (b':path', b'/bad'),
                        (b':scheme', b'https'),
                        (b'content-length', b'4'),
                    ]
                ),
            )
            + encode_frame(FRAME_DATA, b'abc')
        )
        sock.sendto(client.send_stream_data(0, bad_request, fin=True), ('127.0.0.1', port))
        reset_event = None
        for _ in range(6):
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
            for event in client.receive_datagram(data):
                if event.kind == 'reset_stream':
                    reset_event = event
                    break
            if reset_event is not None:
                break
        assert reset_event is not None
        assert reset_event.stream_id == 0
        assert reset_event.detail.error_code == H3_MESSAGE_ERROR
        assert not app_called
    finally:
        sock.close()
        await server.close()
