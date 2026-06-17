from __future__ import annotations

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_CLOSE_SESSION,
    CAPSULE_WT_DRAIN_SESSION,
    H3_ERROR_WT_BUFFERED_STREAM_REJECTED,
    H3_ERROR_WT_SESSION_GONE,
    H3_FRAME_WEBTRANSPORT_STREAM,
    H3_STREAM_TYPE_WEBTRANSPORT,
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
