import unittest

from tigrcorn.protocols.http3.codec import (
    FRAME_HEADERS,
    QPACK_DECODER_STREAM_ERROR,
    QPACK_DECOMPRESSION_FAILED,
    QPACK_ENCODER_STREAM_ERROR,
    encode_frame,
)
from tigrcorn.protocols.http3.qpack import (
    QpackBlocked,
    QpackDecoder,
    QpackDecoderStreamError,
    QpackEncoder,
    decode_qpack_integer,
    encode_duplicate,
    encode_insert_count_increment,
    encode_insert_with_literal_name,
    encode_section_ack,
    encode_qpack_integer,
    encode_set_dynamic_table_capacity,
)
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore, STREAM_TYPE_QPACK_ENCODER, STREAM_TYPE_QPACK_DECODER
from tigrcorn.protocols.http3.codec import HTTP3ConnectionError
from tigrcorn.utils.bytes import encode_quic_varint


class QpackCompletionTests(unittest.TestCase):
    def test_encoder_respects_blocked_stream_limit_until_entries_are_acknowledged(self):
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=1)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=1)
        headers = [(b':method', b'GET'), (b'x-demo', b'value')]

        field1 = encoder.encode_field_section(headers, stream_id=0)
        with self.assertRaises(QpackBlocked):
            decoder.decode_field_section(field1, stream_id=0)

        encoder_stream = encoder.take_encoder_stream_data()
        self.assertTrue(encoder_stream)
        decoder.receive_encoder_stream(encoder_stream)

        field2 = encoder.encode_field_section(headers, stream_id=4)
        encoded_required, _ = decode_qpack_integer(field2, 0, 8)
        self.assertEqual(encoded_required, 0)
        self.assertEqual(decoder.decode_field_section(field2, stream_id=4).headers, headers)

        encoder.receive_decoder_stream(decoder.take_decoder_stream_data())
        field3 = encoder.encode_field_section(headers, stream_id=8)
        section3 = decoder.decode_field_section(field3, stream_id=8)
        self.assertTrue(section3.used_dynamic)
        self.assertEqual(section3.headers, headers)

    def test_encoder_avoids_unsafe_eviction_until_cancel_and_insert_ack(self):
        encoder = QpackEncoder(max_table_capacity=64, blocked_streams=2)
        decoder = QpackDecoder(max_table_capacity=64, blocked_streams=2)

        field1 = encoder.encode_field_section([(b'x-a', b'1')], stream_id=0)
        encoder_stream1 = encoder.take_encoder_stream_data()
        self.assertTrue(encoder_stream1)

        with self.assertRaises(QpackBlocked):
            decoder.decode_field_section(field1, stream_id=0)

        field2 = encoder.encode_field_section([(b'x-b', b'2')], stream_id=4)
        self.assertEqual(encoder.take_encoder_stream_data(), b'')
        self.assertIsNone(encoder.dynamic_table.lookup_dynamic_exact(b'x-b', b'2'))
        self.assertEqual(encoder.dynamic_table.insert_count, 1)
        self.assertIsNotNone(field2)

        decoder.cancel_stream(0)
        decoder.receive_encoder_stream(encoder_stream1)
        encoder.receive_decoder_stream(decoder.take_decoder_stream_data())

        field3 = encoder.encode_field_section([(b'x-b', b'2')], stream_id=8)
        encoder_stream3 = encoder.take_encoder_stream_data()
        self.assertTrue(encoder_stream3)
        self.assertIsNotNone(encoder.dynamic_table.lookup_dynamic_exact(b'x-b', b'2'))
        decoder.receive_encoder_stream(encoder_stream3)
        self.assertEqual(decoder.decode_field_section(field3, stream_id=8).headers, [(b'x-b', b'2')])

    def test_extra_section_ack_is_decoder_stream_error(self):
        encoder = QpackEncoder(max_table_capacity=256, blocked_streams=4)
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=4)

        headers = [(b':method', b'GET'), (b'x-demo', b'value')]
        field = encoder.encode_field_section(headers, stream_id=0)
        decoder.receive_encoder_stream(encoder.take_encoder_stream_data())
        decoder.decode_field_section(field, stream_id=0)
        encoder.receive_decoder_stream(decoder.take_decoder_stream_data())

        with self.assertRaises(QpackDecoderStreamError):
            encoder.receive_decoder_stream(encode_section_ack(0))

    def test_http3_request_backpressure_preserves_body_until_qpack_unblocks(self):
        sender = HTTP3ConnectionCore(role='client')
        receiver = HTTP3ConnectionCore(role='server')
        receiver_settings = receiver.encode_control_stream({1: 256, 6: 1200, 7: 1})
        self.assertIsNone(sender.receive_stream_data(3, receiver_settings, fin=False))

        payload = sender.get_request(0).encode_request(
            [(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https'), (b'x-demo', b'value')],
            body=b'hello',
        )
        request_state = receiver.receive_stream_data(0, payload, fin=True)
        self.assertIsNotNone(request_state)
        assert request_state is not None
        self.assertFalse(request_state.ready)
        self.assertTrue(request_state.blocked_header_sections)
        self.assertEqual(request_state.body, b'')

        encoder_stream = sender.take_encoder_stream_data()
        self.assertTrue(encoder_stream)
        self.assertIsNone(
            receiver.receive_stream_data(2, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER) + encoder_stream, fin=False)
        )
        request_state = receiver.get_request(0).state
        self.assertTrue(request_state.ready)
        self.assertEqual(request_state.body, b'hello')
        self.assertIn((b'x-demo', b'value'), request_state.headers)

    def test_http3_maps_qpack_stream_and_field_section_errors(self):
        core = HTTP3ConnectionCore(role='server')
        core.encode_control_stream({1: 256, 6: 1200, 7: 1})

        with self.assertRaises(HTTP3ConnectionError) as encoder_exc:
            core.receive_stream_data(2, encode_quic_varint(STREAM_TYPE_QPACK_ENCODER) + encode_duplicate(0), fin=False)
        self.assertEqual(encoder_exc.exception.error_code, QPACK_ENCODER_STREAM_ERROR)

        with self.assertRaises(HTTP3ConnectionError) as decoder_exc:
            core.receive_stream_data(
                6,
                encode_quic_varint(STREAM_TYPE_QPACK_DECODER) + encode_insert_count_increment(1),
                fin=False,
            )
        self.assertEqual(decoder_exc.exception.error_code, QPACK_DECODER_STREAM_ERROR)

        invalid_field_section = b'\x00\x00' + encode_qpack_integer(0, 6, 0x80)
        with self.assertRaises(HTTP3ConnectionError) as field_exc:
            core.receive_stream_data(0, encode_frame(FRAME_HEADERS, invalid_field_section), fin=True)
        self.assertEqual(field_exc.exception.error_code, QPACK_DECOMPRESSION_FAILED)

    def test_decoder_handles_post_base_reference(self):
        decoder = QpackDecoder(max_table_capacity=256, blocked_streams=8)
        encoder_stream = b''.join(
            [
                encode_set_dynamic_table_capacity(256),
                encode_insert_with_literal_name(b'x-a', b'0'),
                encode_insert_with_literal_name(b'x-b', b'1'),
                encode_insert_with_literal_name(b'x-c', b'2'),
            ]
        )
        decoder.receive_encoder_stream(encoder_stream)
        required_insert_count = 3
        encoded_required = (required_insert_count % (2 * decoder.dynamic_table.max_entries())) + 1
        prefix = encode_qpack_integer(encoded_required, 8, 0x00) + encode_qpack_integer(0, 7, 0x80)
        post_base_indexed = encode_qpack_integer(0, 4, 0x10)
        section = decoder.decode_field_section(prefix + post_base_indexed, stream_id=0)
        self.assertEqual(section.headers, [(b'x-c', b'2')])
        self.assertTrue(section.used_dynamic)

    def test_decoder_handles_required_insert_count_wraparound(self):
        decoder = QpackDecoder(max_table_capacity=64, blocked_streams=1)
        encoder_stream = bytearray([*encode_set_dynamic_table_capacity(64)])
        for value in range(5):
            encoder_stream.extend(encode_insert_with_literal_name(b'x', str(value).encode('ascii')))
        decoder.receive_encoder_stream(bytes(encoder_stream))

        required_insert_count = 5
        encoded_required = (required_insert_count % (2 * decoder.dynamic_table.max_entries())) + 1
        prefix = encode_qpack_integer(encoded_required, 8, 0x00) + encode_qpack_integer(0, 7, 0x00)
        dynamic_indexed = encode_qpack_integer(0, 6, 0x80)
        section = decoder.decode_field_section(prefix + dynamic_indexed, stream_id=0)
        self.assertEqual(section.headers, [(b'x', b'4')])
        self.assertTrue(section.used_dynamic)
