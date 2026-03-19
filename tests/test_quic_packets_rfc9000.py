import unittest

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


class QuicPacketCodecTests(unittest.TestCase):
    def test_initial_long_header_roundtrip(self):
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
        self.assertIsInstance(decoded, QuicLongHeaderPacket)
        assert isinstance(decoded, QuicLongHeaderPacket)
        self.assertEqual(decoded.packet_type, QuicLongHeaderType.INITIAL)
        self.assertEqual(decoded.destination_connection_id, b'clientcid')
        self.assertEqual(decoded.source_connection_id, b'servercid')
        self.assertEqual(decoded.token, b'token')
        self.assertEqual(decoded.packet_number, b'\x12\x34')
        self.assertEqual(decoded.payload, b'hello-world')
        self.assertEqual(decoded.pn_offset, packet.pn_offset)

    def test_short_header_roundtrip(self):
        packet = QuicShortHeaderPacket(
            destination_connection_id=b'12345678',
            packet_number=b'\x01\x02',
            payload=b'abc',
            key_phase=True,
            spin_bit=True,
        )
        decoded = decode_packet(packet.encode(), destination_connection_id_length=8)
        self.assertIsInstance(decoded, QuicShortHeaderPacket)
        assert isinstance(decoded, QuicShortHeaderPacket)
        self.assertEqual(decoded.destination_connection_id, b'12345678')
        self.assertEqual(decoded.packet_number, b'\x01\x02')
        self.assertEqual(decoded.payload, b'abc')
        self.assertTrue(decoded.key_phase)
        self.assertTrue(decoded.spin_bit)

    def test_version_negotiation_roundtrip(self):
        packet = QuicVersionNegotiationPacket(
            destination_connection_id=b'cidA',
            source_connection_id=b'cidB',
            supported_versions=[1, 0x709A50C4],
        )
        decoded = decode_packet(packet.encode())
        self.assertIsInstance(decoded, QuicVersionNegotiationPacket)
        assert isinstance(decoded, QuicVersionNegotiationPacket)
        self.assertEqual(decoded.destination_connection_id, b'cidA')
        self.assertEqual(decoded.source_connection_id, b'cidB')
        self.assertEqual(decoded.supported_versions, [1, 0x709A50C4])

    def test_retry_roundtrip_and_validation(self):
        original_dcid = bytes.fromhex('8394c8f03e515708')
        packet = QuicRetryPacket(
            version=1,
            destination_connection_id=b'',
            source_connection_id=bytes.fromhex('f067a5502a4262b5'),
            token=b'token',
        )
        encoded = packet.encode(original_destination_connection_id=original_dcid)
        decoded = decode_packet(encoded)
        self.assertIsInstance(decoded, QuicRetryPacket)
        assert isinstance(decoded, QuicRetryPacket)
        self.assertEqual(decoded.token, b'token')
        self.assertTrue(decoded.validate(original_destination_connection_id=original_dcid))

    def test_stateless_reset_parse(self):
        token = b'0123456789abcdef'
        packet = QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=b'xxxxx')
        parsed = parse_stateless_reset(packet.encode(), expected_token=token)
        self.assertEqual(parsed.stateless_reset_token, token)
        self.assertEqual(parsed.unpredictable_bits, b'xxxxx')
