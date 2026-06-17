from __future__ import annotations

from tigrcorn.webtransport.wire import CAPSULE_WT_STREAM, SETTING_WEBTRANSPORT_MAX_SESSIONS, constant_registry_snapshot


def test_webtransport_h2_iana_constants_registered() -> None:
    snapshot = constant_registry_snapshot()

    assert SETTING_WEBTRANSPORT_MAX_SESSIONS == 0x2B60
    assert snapshot["h2_settings"]["SETTINGS_WEBTRANSPORT_MAX_SESSIONS"] == 0x2B60
    assert snapshot["h2_capsules"]["WT_STREAM"] == CAPSULE_WT_STREAM
    assert snapshot["h2_capsules"]["WT_STREAMS_BLOCKED_UNI"] == 0x190B4D44
