from __future__ import annotations

import pytest

from tigrcorn_core.errors import ProtocolError
from tigrcorn_core.utils.bytes import encode_quic_varint
from tigrcorn.protocols.http3.codec import (
    H3_DATAGRAM_ERROR,
    H3_SETTINGS_ERROR,
    HTTP3ConnectionError,
    HTTP3_RESERVED_FRAME_TYPES,
    QPACK_DECODER_STREAM_ERROR,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_H3_DATAGRAM,
    decode_settings,
    encode_settings,
    http3_iana_registry_snapshot,
    is_grease_identifier,
    is_reserved_frame_type,
)
from tigrcorn.webtransport.wire import (
    CAPSULE_WT_CLOSE_SESSION,
    CAPSULE_WT_DRAIN_SESSION,
    H3_ERROR_WT_BUFFERED_STREAM_REJECTED,
    H3_ERROR_WT_SESSION_GONE,
    H3_FRAME_WEBTRANSPORT_STREAM,
    H3_STREAM_TYPE_WEBTRANSPORT,
    SETTING_WT_INITIAL_MAX_DATA,
    SETTING_WT_INITIAL_MAX_STREAMS_BIDI,
    SETTING_WT_INITIAL_MAX_STREAMS_UNI,
    SETTING_WT_MAX_SESSIONS,
    constant_registry_snapshot,
)


def test_webtransport_h3_draft13_iana_settings_frame_stream_error_capsule_constants() -> None:
    snapshot = constant_registry_snapshot()["h3_draft13"]

    assert SETTING_WT_MAX_SESSIONS == 0x14E9CD29
    assert H3_FRAME_WEBTRANSPORT_STREAM == 0x41
    assert H3_STREAM_TYPE_WEBTRANSPORT == 0x54
    assert H3_ERROR_WT_BUFFERED_STREAM_REJECTED == 0x3994BD84
    assert H3_ERROR_WT_SESSION_GONE == 0x170D7B68
    assert snapshot["WT_CLOSE_SESSION"] == CAPSULE_WT_CLOSE_SESSION
    assert snapshot["WT_DRAIN_SESSION"] == CAPSULE_WT_DRAIN_SESSION
    assert snapshot["SETTINGS_WT_INITIAL_MAX_DATA"] == SETTING_WT_INITIAL_MAX_DATA == 0x2B61
    assert snapshot["SETTINGS_WT_INITIAL_MAX_STREAMS_UNI"] == SETTING_WT_INITIAL_MAX_STREAMS_UNI == 0x2B64
    assert snapshot["SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI"] == SETTING_WT_INITIAL_MAX_STREAMS_BIDI == 0x2B65


def test_http3_iana_registry_snapshot_covers_runtime_constants() -> None:
    snapshot = http3_iana_registry_snapshot()

    assert snapshot["settings"]["SETTINGS_ENABLE_CONNECT_PROTOCOL"] == SETTING_ENABLE_CONNECT_PROTOCOL == 0x08
    assert snapshot["settings"]["SETTINGS_H3_DATAGRAM"] == SETTING_H3_DATAGRAM == 0x33
    assert snapshot["settings"]["SETTINGS_WT_MAX_SESSIONS"] == SETTING_WT_MAX_SESSIONS
    assert snapshot["frame_types"]["DATA"] == 0x00
    assert snapshot["frame_types"]["PRIORITY_UPDATE"] == 0xF0700
    assert snapshot["stream_types"]["CONTROL"] == 0x00
    assert snapshot["error_codes"]["H3_DATAGRAM_ERROR"] == H3_DATAGRAM_ERROR == 0x33
    assert snapshot["error_codes"]["H3_SETTINGS_ERROR"] == H3_SETTINGS_ERROR == 0x0109
    assert snapshot["error_codes"]["QPACK_DECODER_STREAM_ERROR"] == QPACK_DECODER_STREAM_ERROR == 0x0202


def test_http3_iana_registry_snapshot_is_isolated_copy() -> None:
    snapshot = http3_iana_registry_snapshot()
    snapshot["settings"]["SETTINGS_H3_DATAGRAM"] = 0

    assert http3_iana_registry_snapshot()["settings"]["SETTINGS_H3_DATAGRAM"] == SETTING_H3_DATAGRAM


def test_http3_settings_reserved_and_duplicate_identifiers_fail_closed() -> None:
    with pytest.raises(ProtocolError, match="reserved HTTP/3 setting"):
        encode_settings({0x00: 1})

    duplicate_payload = (
        encode_quic_varint(SETTING_H3_DATAGRAM)
        + encode_quic_varint(1)
        + encode_quic_varint(SETTING_H3_DATAGRAM)
        + encode_quic_varint(1)
    )
    with pytest.raises(HTTP3ConnectionError) as exc_info:
        decode_settings(duplicate_payload)
    assert exc_info.value.error_code == H3_SETTINGS_ERROR

    reserved_payload = encode_quic_varint(0x02) + encode_quic_varint(1)
    with pytest.raises(HTTP3ConnectionError) as exc_info:
        decode_settings(reserved_payload)
    assert exc_info.value.error_code == H3_SETTINGS_ERROR


def test_http3_frame_registry_reserved_and_grease_detection() -> None:
    assert {0x02, 0x06, 0x08, 0x09} <= set(HTTP3_RESERVED_FRAME_TYPES)
    assert is_reserved_frame_type(0x02)
    assert is_grease_identifier(0x21)
    assert is_grease_identifier(0x40)
    assert not is_reserved_frame_type(0x41)
