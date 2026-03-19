import unittest

from tigrcorn.errors import ProtocolError
from tigrcorn.protocols.http2.hpack import HPACKDecoder, HPACKEncoder, decode_string, encode_string
from tigrcorn.protocols.http3.qpack import QpackBlocked, QpackDecoder, QpackEncoder
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore, STREAM_TYPE_QPACK_ENCODER
from tigrcorn.utils.bytes import encode_quic_varint


class HPACKAdditionalTests(unittest.TestCase):
    def test_huffman_string_roundtrip(self):
        encoded = encode_string(b'custom-header-value', huffman=True)
        self.assertTrue(encoded[0] & 0x80)
        decoded, offset = decode_string(encoded, 0)
        self.assertEqual(decoded, b'custom-header-value')
        self.assertEqual(offset, len(encoded))

    def test_dynamic_table_reuse_and_table_size_update(self):
        encoder = HPACKEncoder(max_table_size=128)
        decoder = HPACKDecoder(max_table_size=128)
        headers = [(b'x-example', b'first'), (b'cache-control', b'no-cache')]
        block1 = encoder.encode_header_block(headers)
        self.assertEqual(decoder.decode_header_block(block1), headers)
        block2 = encoder.encode_header_block(headers)
        self.assertEqual(decoder.decode_header_block(block2), headers)
        self.assertLess(len(block2), len(block1))

        encoder.set_max_table_size(64)
        block3 = encoder.encode_header_block([(b'x-example', b'second')])
        self.assertEqual(decoder.decode_header_block(block3), [(b'x-example', b'second')])
        self.assertEqual(decoder.dynamic_table.max_size, 64)


class QPACKAdditionalTests(unittest.TestCase):
    def test_dynamic_table_roundtrip_and_blocking(self):
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=8)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=8)
        headers = [(b':method', b'GET'), (b'x-demo', b'value')]
        field_section = encoder.encode_field_section(headers, stream_id=0)
        with self.assertRaises(QpackBlocked):
            decoder.decode_field_section(field_section, stream_id=0)
        encoder_stream = encoder.take_encoder_stream_data()
        self.assertTrue(encoder_stream)
        decoder.receive_encoder_stream(encoder_stream)
        self.assertEqual(decoder.decode_field_section(field_section, stream_id=0).headers, headers)
        decoder_stream = decoder.take_decoder_stream_data()
        self.assertTrue(decoder_stream)
        encoder.receive_decoder_stream(decoder_stream)

    def test_http3_core_unblocks_request_after_qpack_encoder_stream(self):
        sender = HTTP3ConnectionCore()
        receiver = HTTP3ConnectionCore()
        receiver_settings = receiver.encode_control_stream({1: 256, 6: 1200, 7: 16})
        self.assertIsNone(sender.receive_stream_data(3, receiver_settings, fin=False))

        payload = sender.get_request(0).encode_request(
            [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https'), (b'x-demo', b'value')],
            b'',
        )
        request_state = receiver.receive_stream_data(0, payload, fin=True)
        self.assertIsNotNone(request_state)
        assert request_state is not None
        self.assertFalse(request_state.ready)
        self.assertEqual(request_state.blocked_header_sections != [], True)

        encoder_stream = sender.take_encoder_stream_data()
        self.assertTrue(encoder_stream)
        self.assertIsNone(receiver.receive_stream_data(2, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER) + encoder_stream, fin=False))
        request_state = receiver.get_request(0).state
        self.assertTrue(request_state.ready)
        self.assertIn((b'x-demo', b'value'), request_state.headers)
        self.assertTrue(receiver.take_decoder_stream_data())

    def test_duplicate_qpack_encoder_stream_rejected(self):
        core = HTTP3ConnectionCore()
        core.encode_control_stream({1: 16, 6: 1200, 7: 1})
        self.assertIsNone(core.receive_stream_data(2, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER), fin=False))
        with self.assertRaises(ProtocolError):
            core.receive_stream_data(6, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER), fin=False)
