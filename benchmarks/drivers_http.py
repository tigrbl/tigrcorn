
from __future__ import annotations

from pathlib import Path

from benchmarks.common import MemoryStreamReader, measure_async, measure_sync
from tigrcorn.protocols.http1.parser import _parse_request_head_bytes, _read_chunked_body
from tigrcorn.protocols.http2.hpack import HPACKDecoder, HPACKEncoder
from tigrcorn.protocols.http3.qpack import QpackBlocked, QpackDecoder, QpackEncoder
from tigrcorn.protocols.http1.keepalive import keep_alive_for_request
from tigrcorn.transports.quic.packets import QuicLongHeaderPacket, QuicLongHeaderType, decode_packet
from tigrcorn.transports.quic.recovery import QuicLossRecovery
from tigrcorn.config.model import ListenerConfig
from tigrcorn.security.tls import build_server_ssl_context

_HTTP11_BASE = (
    b'GET /alpha HTTP/1.1\r\n'
    b'Host: localhost\r\n'
    b'User-Agent: tigrcorn-bench\r\n\r\n'
)
_HTTP11_KEEPALIVE = (
    b'GET /keepalive HTTP/1.1\r\n'
    b'Host: localhost\r\n'
    b'Connection: keep-alive\r\n\r\n'
)
_HTTP11_CHUNKED = (
    b'4\r\nWiki\r\n'
    b'5\r\npedia\r\n'
    b'0\r\nX-Foo: bar\r\n\r\n'
)
_HEADERS = [
    (b':method', b'GET'),
    (b':scheme', b'https'),
    (b':authority', b'example.com'),
    (b':path', b'/resource'),
    (b'user-agent', b'tigrcorn-bench'),
]


def _fixture_paths(source_root: Path) -> tuple[str, str, str]:
    cert = source_root / 'tests/fixtures_certs/interop-localhost-cert.pem'
    key = source_root / 'tests/fixtures_certs/interop-localhost-key.pem'
    ca = source_root / 'tests/fixtures_certs/interop-client-cert.pem'
    return str(cert), str(key), str(ca)


def http11_baseline_driver(profile, *, source_root: Path):
    def operation():
        head = _parse_request_head_bytes(_HTTP11_BASE)
        assert head is not None
        return {
            'connections': 1,
            'correctness': {
                'parsed_head': head.method == 'GET' and head.path == '/alpha' and head.http_version == '1.1',
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def http11_keepalive_driver(profile, *, source_root: Path):
    def operation():
        head = _parse_request_head_bytes(_HTTP11_KEEPALIVE)
        assert head is not None
        return {
            'connections': 1,
            'correctness': {
                'keep_alive': bool(head.keep_alive) and keep_alive_for_request(head.http_version, head.headers),
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def http11_chunked_driver(profile, *, source_root: Path):
    async def operation():
        body = await _read_chunked_body(MemoryStreamReader(_HTTP11_CHUNKED), max_body_size=1024)
        return {
            'connections': 1,
            'correctness': {'chunked_roundtrip': body == b'Wikipedia'},
            'metadata': {'body_size': len(body)},
        }
    return measure_async(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def http2_multiplex_driver(profile, *, source_root: Path):
    stream_count = int(profile.driver_config.get('stream_count', 10))
    def operation():
        encoder = HPACKEncoder()
        decoder = HPACKDecoder()
        block = encoder.encode_header_block(_HEADERS)
        decoded = decoder.decode_header_block(block)
        for index in range(stream_count - 1):
            block = encoder.encode_header_block([(b':path', f'/s/{index}'.encode('ascii')), (b':method', b'GET')])
            decoder.decode_header_block(block)
        return {
            'streams': stream_count,
            'correctness': {
                'hpack_roundtrip': decoded[0] == (b':method', b'GET') and len(decoded) >= 1,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=stream_count)


def http2_tls_driver(profile, *, source_root: Path):
    cert, key, _ca = _fixture_paths(source_root)
    def operation():
        listener = ListenerConfig(
            ssl_certfile=cert,
            ssl_keyfile=key,
            alpn_protocols=['h2', 'http/1.1'],
        )
        context = build_server_ssl_context(listener)
        encoder = HPACKEncoder()
        block = encoder.encode_header_block(_HEADERS)
        decoded = HPACKDecoder().decode_header_block(block)
        return {
            'connections': 1,
            'streams': 1,
            'correctness': {
                'tls_context_built': context is not None,
                'alpn_contains_h2': context is not None and 'h2' in context.alpn_protocols,
                'hpack_roundtrip': decoded[0] == (b':method', b'GET'),
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def http3_clean_driver(profile, *, source_root: Path):
    def operation():
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=16)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=16)
        field_section = encoder.encode_field_section(_HEADERS, stream_id=1)
        encoder_stream = encoder.take_encoder_stream_data()
        if encoder_stream:
            decoder.receive_encoder_stream(encoder_stream)
        section = decoder.decode_field_section(field_section, stream_id=1)
        decoder_stream = decoder.take_decoder_stream_data()
        if decoder_stream:
            encoder.receive_decoder_stream(decoder_stream)
        packet = QuicLongHeaderPacket(
            packet_type=QuicLongHeaderType.INITIAL,
            version=1,
            destination_connection_id=b'clientcid',
            source_connection_id=b'servercid',
            packet_number=b'\x01',
            payload=b'payload',
            token=b'',
        ).encode()
        decoded = decode_packet(packet)
        return {
            'connections': 1,
            'streams': 1,
            'correctness': {
                'qpack_roundtrip': section.headers[0] == (b':method', b'GET'),
                'quic_decode': decoded.payload == b'payload',
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def http3_loss_driver(profile, *, source_root: Path):
    def operation():
        recovery = QuicLossRecovery(max_datagram_size=1200)
        base = 10.0
        for packet_number in range(1, 9):
            recovery.on_packet_sent(packet_number, 1200, packet_space='application', sent_time=base + (packet_number * 0.001))
        acked = recovery.on_ack_received([1, 2, 5], ack_delay=0.001, now=base + 0.050, packet_space='application')
        lost = recovery.detect_lost_packets(now=base + 0.070, packet_space='application')
        snapshot = recovery.snapshot()
        try:
            encoder = QpackEncoder(max_table_capacity=256, blocked_streams=1)
            decoder = QpackDecoder(max_table_capacity=256, blocked_streams=1)
            field_section = encoder.encode_field_section([(b'cache-control', b'max-age=0')], stream_id=1)
            decoder.decode_field_section(field_section, stream_id=1)
            blocked = False
        except QpackBlocked:
            blocked = True
        return {
            'connections': 1,
            'streams': 1,
            'protocol_stalls': {
                'lost_packets': len(lost),
                'acked_packets': len(acked),
                'qpack_blocked': 1 if blocked else 0,
            },
            'correctness': {
                'loss_detected': len(lost) > 0,
                'pto_positive': recovery.pto_timeout(packet_space='application') > 0.0,
                'snapshot_valid': snapshot.congestion_window >= recovery.minimum_congestion_window,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)
