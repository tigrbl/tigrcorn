import pytest

from tigrcorn.security.tls13.extensions import TransportParameters
from tigrcorn_core.errors import ProtocolError
from tigrcorn_transports.quic.streams import (
    QuicResetStreamAtFrame,
    decode_frame,
    encode_frame,
    validate_frame_for_packet_space,
)


def test_reset_stream_at_transport_parameter_roundtrip() -> None:
    decoded = TransportParameters.from_bytes(TransportParameters(reset_stream_at=True).to_bytes())
    assert decoded.reset_stream_at is True


def test_reset_stream_at_is_monotonic_for_zero_rtt() -> None:
    previous = TransportParameters(reset_stream_at=True)
    assert previous.is_0rtt_compatible_with(TransportParameters(reset_stream_at=True))
    assert not previous.is_0rtt_compatible_with(TransportParameters(reset_stream_at=False))


def test_reset_stream_at_frame_roundtrip() -> None:
    frame = QuicResetStreamAtFrame(stream_id=4, error_code=9, final_size=12, reliable_size=7)
    decoded, offset = decode_frame(encode_frame(frame))
    assert decoded == frame
    assert offset == len(encode_frame(frame))


def test_reset_stream_at_reliable_size_cannot_exceed_final_size() -> None:
    with pytest.raises(ProtocolError, match="reliable size"):
        QuicResetStreamAtFrame(stream_id=4, error_code=9, final_size=6, reliable_size=7)


def test_reset_stream_at_packet_space_legality() -> None:
    frame = QuicResetStreamAtFrame(stream_id=4, error_code=0, final_size=0, reliable_size=0)
    validate_frame_for_packet_space(frame, "application")
    with pytest.raises(ProtocolError):
        validate_frame_for_packet_space(frame, "initial")
