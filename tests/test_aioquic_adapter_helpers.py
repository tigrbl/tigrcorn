from __future__ import annotations

from tests.fixtures_third_party._aioquic_utils import (
    detect_local_control_stream_id,
    detect_peer_qpack_streams,
    detect_retry_observed,
    encode_goaway_frame,
    env_flag,
    header_map,
    header_pairs_to_text,
    quic_varint_encode,
    received_settings,
    session_ticket_allows_early_data,
)


class _DummyH3:
    def __init__(self) -> None:
        self._local_control_stream_id = 2
        self._peer_qpack_encoder_stream_id = 7
        self._peer_qpack_decoder_stream_id = 11
        self.received_settings = {0x08: 1}


class _DummyQuicRetry:
    def __init__(self) -> None:
        self._retry_count = 1
        self._retry_source_connection_id = b"retry-source"


class _DummySessionTicket:
    def __init__(self, max_early_data_size: int) -> None:
        self.max_early_data_size = max_early_data_size


def test_env_flag_truth_table(monkeypatch) -> None:
    monkeypatch.setenv("AIOQUIC_FLAG", "true")
    assert env_flag("AIOQUIC_FLAG") is True
    monkeypatch.setenv("AIOQUIC_FLAG", "On")
    assert env_flag("AIOQUIC_FLAG") is True
    monkeypatch.setenv("AIOQUIC_FLAG", "0")
    assert env_flag("AIOQUIC_FLAG") is False


def test_quic_varint_encode_matches_rfc_examples() -> None:
    assert quic_varint_encode(0) == b"\x00"
    assert quic_varint_encode(63) == b"\x3f"
    assert quic_varint_encode(64) == b"\x40\x40"
    assert quic_varint_encode(15293) == bytes.fromhex("7bbd")
    assert quic_varint_encode(494878333) == bytes.fromhex("9d7f3e7d")
    assert quic_varint_encode(151288809941952652) == bytes.fromhex("c2197c5eff14e88c")


def test_encode_goaway_frame_includes_http3_frame_length() -> None:
    assert encode_goaway_frame(0) == bytes.fromhex("070100")
    assert encode_goaway_frame(4) == bytes.fromhex("070104")


def test_header_helpers_normalize_byte_pairs() -> None:
    headers = [(b":status", b"200"), (b"server", b"tigrcorn")]
    assert header_pairs_to_text(headers) == [(":status", "200"), ("server", "tigrcorn")]
    assert header_map(headers) == {":status": "200", "server": "tigrcorn"}


def test_http3_snapshot_helpers_detect_control_and_qpack_streams() -> None:
    dummy = _DummyH3()
    assert detect_local_control_stream_id(dummy) == 2
    assert detect_peer_qpack_streams(dummy) == (True, True)
    assert received_settings(dummy) == {0x08: 1}


def test_detect_retry_observed_scans_common_aioquic_state() -> None:
    assert detect_retry_observed(_DummyQuicRetry()) is True
    assert detect_retry_observed(object()) is False


def test_session_ticket_allows_early_data_for_object_and_mapping() -> None:
    assert session_ticket_allows_early_data(_DummySessionTicket(16384)) is True
    assert session_ticket_allows_early_data(_DummySessionTicket(0)) is False
    assert session_ticket_allows_early_data({"max_early_data_size": 8192}) is True
    assert session_ticket_allows_early_data({"max_early_data_size": 0}) is False
    assert session_ticket_allows_early_data({"ticket": "opaque"}) is True
    assert session_ticket_allows_early_data(None) is False
