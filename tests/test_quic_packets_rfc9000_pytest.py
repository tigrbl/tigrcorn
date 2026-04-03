
import pytest
from tigrcorn.transports.quic.packets import (
    QuicLongHeaderPacket,
    QuicLongHeaderType,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicStatelessResetPacket,
    QuicVersionNegotiationPacket,
    decode_packet,
    parse_stateless_reset,
)



def test_initial_long_header_roundtrip():
    packet = QuicLongHeaderPacket(
        packet_type=QuicLongHeaderType.INITIAL,
        version=1,
        destination_connection_id=b'clientcid',
        source_connection_id=b'servercid',
        token=b'token',
        packet_number=b'\x12\x34',
        payload=b'hello-world',
    )
    decoded = decode_packet(packet.encode())
    assert isinstance(decoded, QuicLongHeaderPacket)
    assert isinstance(decoded, QuicLongHeaderPacket)
    assert decoded.packet_type == QuicLongHeaderType.INITIAL
    assert decoded.destination_connection_id == b'clientcid'
    assert decoded.source_connection_id == b'servercid'
    assert decoded.token == b'token'
    assert decoded.packet_number == b'\x12\x34'
    assert decoded.payload == b'hello-world'
    assert decoded.pn_offset == packet.pn_offset
def test_short_header_roundtrip():
    packet = QuicShortHeaderPacket(
        destination_connection_id=b'12345678',
        packet_number=b'\x01\x02',
        payload=b'abc',
        key_phase=True,
        spin_bit=True,
    )
    decoded = decode_packet(packet.encode(), destination_connection_id_length=8)
    assert isinstance(decoded, QuicShortHeaderPacket)
    assert isinstance(decoded, QuicShortHeaderPacket)
    assert decoded.destination_connection_id == b'12345678'
    assert decoded.packet_number == b'\x01\x02'
    assert decoded.payload == b'abc'
    assert decoded.key_phase
    assert decoded.spin_bit
def test_version_negotiation_roundtrip():
    packet = QuicVersionNegotiationPacket(
        destination_connection_id=b'cidA',
        source_connection_id=b'cidB',
        supported_versions=[1, 0x709A50C4],
    )
    decoded = decode_packet(packet.encode())
    assert isinstance(decoded, QuicVersionNegotiationPacket)
    assert isinstance(decoded, QuicVersionNegotiationPacket)
    assert decoded.destination_connection_id == b'cidA'
    assert decoded.source_connection_id == b'cidB'
    assert decoded.supported_versions == [1, 0x709A50C4]
def test_retry_roundtrip_and_validation():
    original_dcid = bytes.fromhex('8394c8f03e515708')
    packet = QuicRetryPacket(
        version=1,
        destination_connection_id=b'',
        source_connection_id=bytes.fromhex('f067a5502a4262b5'),
        token=b'token',
    )
    encoded = packet.encode(original_destination_connection_id=original_dcid)
    decoded = decode_packet(encoded)
    assert isinstance(decoded, QuicRetryPacket)
    assert isinstance(decoded, QuicRetryPacket)
    assert decoded.token == b'token'
    assert decoded.validate(original_destination_connection_id=original_dcid)
def test_stateless_reset_parse():
    token = b'0123456789abcdef'
    packet = QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=b'xxxxx')
    parsed = parse_stateless_reset(packet.encode(), expected_token=token)
    assert parsed.stateless_reset_token == token
    assert parsed.unpredictable_bits == b'xxxxx'