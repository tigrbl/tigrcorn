from __future__ import annotations

from tigrcorn.protocols.http3.codec import (
    H3_DATAGRAM_ERROR,
    H3_SETTINGS_ERROR,
    QPACK_DECODER_STREAM_ERROR,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_H3_DATAGRAM,
    http3_iana_registry_snapshot,
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
