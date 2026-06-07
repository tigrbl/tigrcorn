from __future__ import annotations

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint, pack_varbytes, unpack_varbytes
from .constants import *
from .frames import *

def encode_frame(frame: QuicFrame) -> bytes:
    if frame == FRAME_PADDING:
        return b'\x00'
    if frame == FRAME_PING:
        return encode_quic_varint(FRAME_PING)
    if isinstance(frame, QuicStreamFrame):
        flags = 0x02 | (0x01 if frame.fin else 0)
        payload = bytearray()
        payload.extend(encode_quic_varint(FRAME_STREAM | flags | (0x04 if frame.offset else 0x00)))
        payload.extend(encode_quic_varint(frame.stream_id))
        if frame.offset:
            payload.extend(encode_quic_varint(frame.offset))
        payload.extend(encode_quic_varint(len(frame.data)))
        payload.extend(frame.data)
        return bytes(payload)
    if isinstance(frame, QuicAckFrame):
        payload = bytearray()
        payload.extend(encode_quic_varint(FRAME_ACK))
        payload.extend(encode_quic_varint(frame.largest_acked))
        payload.extend(encode_quic_varint(frame.ack_delay))
        payload.extend(encode_quic_varint(len(frame.ack_ranges)))
        payload.extend(encode_quic_varint(frame.first_ack_range))
        for gap, ack_range_length in frame.ack_ranges:
            payload.extend(encode_quic_varint(gap))
            payload.extend(encode_quic_varint(ack_range_length))
        return bytes(payload)
    if isinstance(frame, QuicResetStreamFrame):
        return (
            encode_quic_varint(FRAME_RESET_STREAM)
            + encode_quic_varint(frame.stream_id)
            + encode_quic_varint(frame.error_code)
            + encode_quic_varint(frame.final_size)
        )
    if isinstance(frame, QuicStopSendingFrame):
        return encode_quic_varint(FRAME_STOP_SENDING) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.error_code)
    if isinstance(frame, QuicCryptoFrame):
        return encode_quic_varint(FRAME_CRYPTO) + encode_quic_varint(frame.offset) + pack_varbytes(frame.data)
    if isinstance(frame, QuicNewTokenFrame):
        return encode_quic_varint(FRAME_NEW_TOKEN) + pack_varbytes(frame.token)
    if isinstance(frame, QuicMaxDataFrame):
        return encode_quic_varint(FRAME_MAX_DATA) + encode_quic_varint(frame.maximum_data)
    if isinstance(frame, QuicMaxStreamDataFrame):
        return encode_quic_varint(FRAME_MAX_STREAM_DATA) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.maximum_data)
    if isinstance(frame, QuicMaxStreamsFrame):
        frame_type = FRAME_MAX_STREAMS_BIDI if frame.bidirectional else FRAME_MAX_STREAMS_UNI
        return encode_quic_varint(frame_type) + encode_quic_varint(frame.maximum_streams)
    if isinstance(frame, QuicDataBlockedFrame):
        return encode_quic_varint(FRAME_DATA_BLOCKED) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicStreamDataBlockedFrame):
        return encode_quic_varint(FRAME_STREAM_DATA_BLOCKED) + encode_quic_varint(frame.stream_id) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicStreamsBlockedFrame):
        frame_type = FRAME_STREAMS_BLOCKED_BIDI if frame.bidirectional else FRAME_STREAMS_BLOCKED_UNI
        return encode_quic_varint(frame_type) + encode_quic_varint(frame.limit)
    if isinstance(frame, QuicNewConnectionIdFrame):
        return (
            encode_quic_varint(FRAME_NEW_CONNECTION_ID)
            + encode_quic_varint(frame.sequence)
            + encode_quic_varint(frame.retire_prior_to)
            + pack_varbytes(frame.connection_id)
            + frame.stateless_reset_token
        )
    if isinstance(frame, QuicRetireConnectionIdFrame):
        return encode_quic_varint(FRAME_RETIRE_CONNECTION_ID) + encode_quic_varint(frame.sequence)
    if isinstance(frame, QuicPathChallengeFrame):
        return encode_quic_varint(FRAME_PATH_CHALLENGE) + frame.data
    if isinstance(frame, QuicPathResponseFrame):
        return encode_quic_varint(FRAME_PATH_RESPONSE) + frame.data
    if isinstance(frame, QuicHandshakeDoneFrame):
        return encode_quic_varint(FRAME_HANDSHAKE_DONE)
    if isinstance(frame, QuicDatagramFrame):
        return encode_quic_varint(FRAME_DATAGRAM | 0x01) + pack_varbytes(frame.data)
    if isinstance(frame, QuicConnectionCloseFrame):
        reason = frame.reason.encode('utf-8')
        frame_type = FRAME_CONNECTION_CLOSE_APP if frame.application else FRAME_CONNECTION_CLOSE
        return (
            encode_quic_varint(frame_type)
            + encode_quic_varint(frame.error_code)
            + encode_quic_varint(frame.frame_type)
            + pack_varbytes(reason)
        )
    raise TypeError(f'unsupported QUIC frame: {type(frame)!r}')


def decode_frame(data: bytes, offset: int = 0) -> tuple[QuicFrame, int]:
    frame_type, offset = decode_quic_varint(data, offset)
    if frame_type == FRAME_PADDING:
        return FRAME_PADDING, offset
    if frame_type == FRAME_PING:
        return FRAME_PING, offset
    if frame_type & 0xF8 == FRAME_STREAM:
        fin = bool(frame_type & 0x01)
        has_length = bool(frame_type & 0x02)
        has_offset = bool(frame_type & 0x04)
        stream_id, offset = decode_quic_varint(data, offset)
        frame_offset = 0
        if has_offset:
            frame_offset, offset = decode_quic_varint(data, offset)
        if has_length:
            length, offset = decode_quic_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise ProtocolError('truncated STREAM frame payload')
            payload = data[offset:end]
            offset = end
        else:
            payload = data[offset:]
            offset = len(data)
        return QuicStreamFrame(stream_id=stream_id, offset=frame_offset, fin=fin, data=payload), offset
    if frame_type == FRAME_ACK:
        largest_acked, offset = decode_quic_varint(data, offset)
        ack_delay, offset = decode_quic_varint(data, offset)
        ack_range_count, offset = decode_quic_varint(data, offset)
        first_ack_range, offset = decode_quic_varint(data, offset)
        ack_ranges: list[tuple[int, int]] = []
        for _ in range(ack_range_count):
            gap, offset = decode_quic_varint(data, offset)
            ack_range_length, offset = decode_quic_varint(data, offset)
            ack_ranges.append((gap, ack_range_length))
        return QuicAckFrame(largest_acked=largest_acked, ack_delay=ack_delay, first_ack_range=first_ack_range, ack_ranges=ack_ranges), offset
    if frame_type == FRAME_RESET_STREAM:
        stream_id, offset = decode_quic_varint(data, offset)
        error_code, offset = decode_quic_varint(data, offset)
        final_size, offset = decode_quic_varint(data, offset)
        return QuicResetStreamFrame(stream_id=stream_id, error_code=error_code, final_size=final_size), offset
    if frame_type == FRAME_STOP_SENDING:
        stream_id, offset = decode_quic_varint(data, offset)
        error_code, offset = decode_quic_varint(data, offset)
        return QuicStopSendingFrame(stream_id=stream_id, error_code=error_code), offset
    if frame_type == FRAME_CRYPTO:
        crypto_offset, offset = decode_quic_varint(data, offset)
        payload, offset = unpack_varbytes(data, offset)
        return QuicCryptoFrame(offset=crypto_offset, data=payload), offset
    if frame_type == FRAME_NEW_TOKEN:
        token, offset = unpack_varbytes(data, offset)
        return QuicNewTokenFrame(token=token), offset
    if frame_type == FRAME_MAX_DATA:
        maximum_data, offset = decode_quic_varint(data, offset)
        return QuicMaxDataFrame(maximum_data=maximum_data), offset
    if frame_type == FRAME_MAX_STREAM_DATA:
        stream_id, offset = decode_quic_varint(data, offset)
        maximum_data, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamDataFrame(stream_id=stream_id, maximum_data=maximum_data), offset
    if frame_type == FRAME_MAX_STREAMS_BIDI:
        maximum_streams, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamsFrame(maximum_streams=maximum_streams, bidirectional=True), offset
    if frame_type == FRAME_MAX_STREAMS_UNI:
        maximum_streams, offset = decode_quic_varint(data, offset)
        return QuicMaxStreamsFrame(maximum_streams=maximum_streams, bidirectional=False), offset
    if frame_type == FRAME_DATA_BLOCKED:
        limit, offset = decode_quic_varint(data, offset)
        return QuicDataBlockedFrame(limit=limit), offset
    if frame_type == FRAME_STREAM_DATA_BLOCKED:
        stream_id, offset = decode_quic_varint(data, offset)
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamDataBlockedFrame(stream_id=stream_id, limit=limit), offset
    if frame_type == FRAME_STREAMS_BLOCKED_BIDI:
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamsBlockedFrame(limit=limit, bidirectional=True), offset
    if frame_type == FRAME_STREAMS_BLOCKED_UNI:
        limit, offset = decode_quic_varint(data, offset)
        return QuicStreamsBlockedFrame(limit=limit, bidirectional=False), offset
    if frame_type == FRAME_NEW_CONNECTION_ID:
        sequence, offset = decode_quic_varint(data, offset)
        retire_prior_to, offset = decode_quic_varint(data, offset)
        connection_id, offset = unpack_varbytes(data, offset)
        if offset + 16 > len(data):
            raise ProtocolError('truncated NEW_CONNECTION_ID frame')
        token = data[offset:offset + 16]
        offset += 16
        return QuicNewConnectionIdFrame(sequence=sequence, retire_prior_to=retire_prior_to, connection_id=connection_id, stateless_reset_token=token), offset
    if frame_type == FRAME_RETIRE_CONNECTION_ID:
        sequence, offset = decode_quic_varint(data, offset)
        return QuicRetireConnectionIdFrame(sequence=sequence), offset
    if frame_type == FRAME_PATH_CHALLENGE:
        if offset + 8 > len(data):
            raise ProtocolError('truncated PATH_CHALLENGE frame')
        payload = data[offset:offset + 8]
        offset += 8
        return QuicPathChallengeFrame(payload), offset
    if frame_type == FRAME_PATH_RESPONSE:
        if offset + 8 > len(data):
            raise ProtocolError('truncated PATH_RESPONSE frame')
        payload = data[offset:offset + 8]
        offset += 8
        return QuicPathResponseFrame(payload), offset
    if frame_type == FRAME_HANDSHAKE_DONE:
        return QuicHandshakeDoneFrame(), offset
    if frame_type & 0xFE == FRAME_DATAGRAM:
        if frame_type & 0x01:
            payload, offset = unpack_varbytes(data, offset)
        else:
            payload = data[offset:]
            offset = len(data)
        return QuicDatagramFrame(payload), offset
    if frame_type in {FRAME_CONNECTION_CLOSE, FRAME_CONNECTION_CLOSE_APP}:
        error_code, offset = decode_quic_varint(data, offset)
        frame_type_value_field, offset = decode_quic_varint(data, offset)
        reason, offset = unpack_varbytes(data, offset)
        return (
            QuicConnectionCloseFrame(
                error_code=error_code,
                frame_type=frame_type_value_field,
                reason=reason.decode('utf-8', 'replace'),
                application=(frame_type == FRAME_CONNECTION_CLOSE_APP),
            ),
            offset,
        )
    raise ProtocolError(f'unsupported QUIC frame type: {frame_type}')
