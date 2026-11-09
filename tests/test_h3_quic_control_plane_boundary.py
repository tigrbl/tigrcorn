from __future__ import annotations

from types import SimpleNamespace

import pytest

from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.codec import (
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    QPACK_DECODER_STREAM_ERROR,
    QPACK_DECOMPRESSION_FAILED,
    QPACK_ENCODER_STREAM_ERROR,
    STREAM_TYPE_CONTROL,
    HTTP3ConnectionError,
    decode_frame,
    decode_settings,
    encode_frame,
)
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.qpack import (
    QpackBlocked,
    QpackDecoder,
    QpackDecoderStreamError,
    QpackEncoder,
    decode_qpack_integer,
    encode_duplicate,
    encode_insert_count_increment,
)
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore, STREAM_TYPE_QPACK_DECODER, STREAM_TYPE_QPACK_ENCODER
from tigrcorn.transports.quic.crypto import (
    compute_retry_integrity_tag,
    derive_initial_packet_protection_keys,
    protect_quic_packet,
    update_quic_secret,
)
from tigrcorn.transports.quic.packets import QuicRetryPacket, decode_packet
from tigrcorn.utils.bytes import decode_quic_varint, encode_quic_varint


def _http3_handler() -> HTTP3DatagramHandler:
    async def app(scope, receive, send):
        return None

    return HTTP3DatagramHandler(
        app=app,
        config=default_config(),
        listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
        access_logger=AccessLogger(configure_logging('warning'), enabled=False),
    )


def test_quic_tls_mapping_derives_distinct_client_and_server_initial_keys() -> None:
    cid = bytes.fromhex('8394c8f03e515708')
    client, server = derive_initial_packet_protection_keys(cid)
    assert client.secret != server.secret
    assert client.key != server.key
    assert client.iv != server.iv
    assert client.hp != server.hp


def test_quic_tls_mapping_protects_initial_packet_and_rotates_secret() -> None:
    cid = bytes.fromhex('8394c8f03e515708')
    client, _server = derive_initial_packet_protection_keys(cid)
    payload = b'control-plane-payload'
    header = bytes.fromhex('c300000001088394c8f03e5157080000449e00000002')
    packet = protect_quic_packet(header, payload, packet_number=2, pn_offset=18, keys=client)
    assert packet != header + payload
    next_secret = update_quic_secret(client.secret)
    assert next_secret != client.secret


def test_quic_retry_token_integrity_accepts_correct_original_destination_cid() -> None:
    original_dcid = bytes.fromhex('8394c8f03e515708')
    packet = QuicRetryPacket(
        version=1,
        destination_connection_id=b'',
        source_connection_id=bytes.fromhex('f067a5502a4262b5'),
        token=b'control-plane-token',
    )
    encoded = packet.encode(original_destination_connection_id=original_dcid)
    decoded = decode_packet(encoded)
    assert isinstance(decoded, QuicRetryPacket)
    assert decoded.validate(original_destination_connection_id=original_dcid) is True


def test_quic_retry_token_integrity_rejects_mismatched_original_destination_cid() -> None:
    original_dcid = bytes.fromhex('8394c8f03e515708')
    packet = QuicRetryPacket(
        version=1,
        destination_connection_id=b'',
        source_connection_id=bytes.fromhex('f067a5502a4262b5'),
        token=b'control-plane-token',
    )
    encoded = packet.encode(original_destination_connection_id=original_dcid)
    decoded = decode_packet(encoded)
    assert isinstance(decoded, QuicRetryPacket)
    assert decoded.validate(original_destination_connection_id=b'wrongcid0') is False
    assert compute_retry_integrity_tag(encoded[:-16], original_dcid) != compute_retry_integrity_tag(encoded[:-16], b'wrongcid0')


def test_http3_control_plane_emits_control_stream_settings_and_goaway() -> None:
    core = HTTP3ConnectionCore()
    control_payload = core.encode_control_stream({1: 0, 6: 1200})
    stream_type, offset = decode_quic_varint(control_payload, 0)
    assert stream_type == STREAM_TYPE_CONTROL
    frame, _ = decode_frame(control_payload, offset)
    assert frame.frame_type == FRAME_SETTINGS
    assert decode_settings(frame.payload) == {1: 0, 6: 1200}

    goaway = core.encode_goaway(33)
    frame, _ = decode_frame(goaway, 0)
    assert frame.frame_type == FRAME_GOAWAY
    stream_id, _ = decode_quic_varint(frame.payload, 0)
    assert stream_id == 33


def test_http3_control_plane_rejects_invalid_headers_and_truncated_frames() -> None:
    handler = _http3_handler()
    with pytest.raises(ProtocolError):
        handler._validate_request_headers([(b':method', b'GET'), (b':method', b'POST'), (b':path', b'/'), (b':scheme', b'https')])
    with pytest.raises(ProtocolError):
        handler._validate_request_headers([(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https'), (b'connection', b'close')])
    with pytest.raises(ProtocolError):
        decode_frame(encode_quic_varint(1) + encode_quic_varint(5) + b'ab')


def test_qpack_error_handling_blocks_until_encoder_stream_arrives() -> None:
    encoder = QpackEncoder(max_table_capacity=256, blocked_streams=1)
    decoder = QpackDecoder(max_table_capacity=256, blocked_streams=1)
    headers = [(b':method', b'GET'), (b'x-demo', b'value')]

    field = encoder.encode_field_section(headers, stream_id=0)
    with pytest.raises(QpackBlocked):
        decoder.decode_field_section(field, stream_id=0)

    encoder_stream = encoder.take_encoder_stream_data()
    assert encoder_stream
    decoder.receive_encoder_stream(encoder_stream)
    resolved = decoder.decode_field_section(encoder.encode_field_section(headers, stream_id=4), stream_id=4)
    assert resolved.headers == headers


def test_qpack_error_handling_maps_encoder_decoder_and_field_section_failures() -> None:
    core = HTTP3ConnectionCore(role='server')
    core.encode_control_stream({1: 256, 6: 1200, 7: 1})

    with pytest.raises(HTTP3ConnectionError) as encoder_exc:
        core.receive_stream_data(2, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER) + encode_duplicate(0), fin=False)
    assert encoder_exc.value.error_code == QPACK_ENCODER_STREAM_ERROR

    with pytest.raises(HTTP3ConnectionError) as decoder_exc:
        core.receive_stream_data(
            6,
            encode_quic_varint(STREAM_TYPE_QPACK_DECODER) + encode_insert_count_increment(1),
            fin=False,
        )
    assert decoder_exc.value.error_code == QPACK_DECODER_STREAM_ERROR

    invalid_field_section = b'\x00\x00' + encode_quic_varint(0x80)
    with pytest.raises(HTTP3ConnectionError) as field_exc:
        core.receive_stream_data(0, encode_frame(FRAME_HEADERS, invalid_field_section), fin=True)
    assert field_exc.value.error_code == QPACK_DECOMPRESSION_FAILED


def test_qpack_error_handling_rejects_duplicate_section_ack() -> None:
    encoder = QpackEncoder(max_table_capacity=256, blocked_streams=4)
    decoder = QpackDecoder(max_table_capacity=256, blocked_streams=4)
    headers = [(b':method', b'GET'), (b'x-demo', b'value')]

    field = encoder.encode_field_section(headers, stream_id=0)
    decoder.receive_encoder_stream(encoder.take_encoder_stream_data())
    decoder.decode_field_section(field, stream_id=0)
    encoder.receive_decoder_stream(decoder.take_decoder_stream_data())

    with pytest.raises(QpackDecoderStreamError):
        encoder.receive_decoder_stream(b'\x80')
