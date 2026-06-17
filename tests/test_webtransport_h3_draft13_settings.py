from __future__ import annotations

from tigrcorn.protocols.http3.codec import SETTING_ENABLE_WEBTRANSPORT, SETTING_WT_MAX_SESSIONS
from tigrcorn.webtransport.wire import (
    SETTING_ENABLE_WEBTRANSPORT_LEGACY,
    h3_compat_settings,
    h3_draft13_settings,
    h3_draft13_transport_capable,
)


def test_webtransport_h3_draft13_settings_wt_max_sessions() -> None:
    settings = h3_draft13_settings(8)

    assert settings[SETTING_WT_MAX_SESSIONS] == 8
    assert h3_draft13_transport_capable(settings)


def test_webtransport_h3_legacy_enable_webtransport_not_canonical() -> None:
    canonical = h3_draft13_settings(8)
    compat = h3_compat_settings(8)

    assert SETTING_ENABLE_WEBTRANSPORT == SETTING_ENABLE_WEBTRANSPORT_LEGACY
    assert SETTING_ENABLE_WEBTRANSPORT_LEGACY not in canonical
    assert compat[SETTING_ENABLE_WEBTRANSPORT_LEGACY] == 1
