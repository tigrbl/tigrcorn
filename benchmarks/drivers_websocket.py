
from __future__ import annotations

import zlib

from benchmarks.common import measure_sync
from tigrcorn.protocols.http2.hpack import HPACKDecoder, HPACKEncoder
from tigrcorn.protocols.http3.qpack import QpackDecoder, QpackEncoder
from tigrcorn.protocols.websocket.frames import decode_frame, encode_frame

_TEXT = b'hello websocket benchmark'
_CONNECT_HEADERS_H2 = [
    (b':method', b'CONNECT'),
    (b':protocol', b'websocket'),
    (b':scheme', b'https'),
    (b':authority', b'example.com'),
    (b':path', b'/chat'),
]
_CONNECT_HEADERS_H3 = [
    (b':method', b'CONNECT'),
    (b':protocol', b'websocket'),
    (b':scheme', b'https'),
    (b':authority', b'example.com'),
    (b':path', b'/chat'),
]


def _compress(payload: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(payload) + compressor.flush(zlib.Z_SYNC_FLUSH)[:-4]


def _decompress(payload: bytes) -> bytes:
    decompressor = zlib.decompressobj(wbits=-15)
    return decompressor.decompress(payload + b'\x00\x00\xff\xff')


def ws_http11_driver(profile, *, source_root):
    def operation():
        data = encode_frame(0x1, _TEXT, masked=True, mask_key=b'\x01\x02\x03\x04')
        frame = decode_frame(data, expect_masked=True)
        return {'connections': 1, 'correctness': {'frame_roundtrip': frame.payload == _TEXT}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_http11_deflate_driver(profile, *, source_root):
    def operation():
        compressed = _compress(_TEXT)
        data = encode_frame(0x1, compressed, masked=True, mask_key=b'\x05\x06\x07\x08', rsv1=True)
        frame = decode_frame(data, expect_masked=True, allow_rsv1=True)
        return {'connections': 1, 'correctness': {'deflate_roundtrip': _decompress(frame.payload) == _TEXT and frame.rsv1}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_http2_driver(profile, *, source_root):
    def operation():
        block = HPACKEncoder().encode_header_block(_CONNECT_HEADERS_H2)
        headers = HPACKDecoder().decode_header_block(block)
        frame = decode_frame(encode_frame(0x1, _TEXT, masked=False), expect_masked=False)
        return {'connections': 1, 'streams': 1, 'correctness': {'extended_connect_block': headers[0] == (b':method', b'CONNECT'), 'frame_roundtrip': frame.payload == _TEXT}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_http2_deflate_driver(profile, *, source_root):
    def operation():
        block = HPACKEncoder().encode_header_block(_CONNECT_HEADERS_H2)
        headers = HPACKDecoder().decode_header_block(block)
        compressed = _compress(_TEXT)
        frame = decode_frame(encode_frame(0x1, compressed, masked=False, rsv1=True), expect_masked=False, allow_rsv1=True)
        return {'connections': 1, 'streams': 1, 'correctness': {'extended_connect_block': headers[0] == (b':method', b'CONNECT'), 'deflate_roundtrip': _decompress(frame.payload) == _TEXT}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_http3_driver(profile, *, source_root):
    def operation():
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=4)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=4)
        field_section = encoder.encode_field_section(_CONNECT_HEADERS_H3, stream_id=1)
        enc = encoder.take_encoder_stream_data()
        if enc:
            decoder.receive_encoder_stream(enc)
        headers = decoder.decode_field_section(field_section, stream_id=1).headers
        dec = decoder.take_decoder_stream_data()
        if dec:
            encoder.receive_decoder_stream(dec)
        frame = decode_frame(encode_frame(0x1, _TEXT, masked=False), expect_masked=False)
        return {'connections': 1, 'streams': 1, 'correctness': {'extended_connect_block': headers[0] == (b':method', b'CONNECT'), 'frame_roundtrip': frame.payload == _TEXT}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_http3_deflate_driver(profile, *, source_root):
    def operation():
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=4)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=4)
        field_section = encoder.encode_field_section(_CONNECT_HEADERS_H3, stream_id=1)
        enc = encoder.take_encoder_stream_data()
        if enc:
            decoder.receive_encoder_stream(enc)
        headers = decoder.decode_field_section(field_section, stream_id=1).headers
        compressed = _compress(_TEXT)
        frame = decode_frame(encode_frame(0x1, compressed, masked=False, rsv1=True), expect_masked=False, allow_rsv1=True)
        return {'connections': 1, 'streams': 1, 'correctness': {'extended_connect_block': headers[0] == (b':method', b'CONNECT'), 'deflate_roundtrip': _decompress(frame.payload) == _TEXT}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def ws_fanout_driver(profile, *, source_root):
    fanout = int(profile.driver_config.get('fanout', 32))
    def operation():
        frame = encode_frame(0x1, _TEXT, masked=False)
        delivered = 0
        for _ in range(fanout):
            decoded = decode_frame(frame, expect_masked=False)
            if decoded.payload == _TEXT:
                delivered += 1
        return {'connections': fanout, 'correctness': {'fanout_delivery': delivered == fanout}, 'metadata': {'fanout': fanout}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=fanout)
