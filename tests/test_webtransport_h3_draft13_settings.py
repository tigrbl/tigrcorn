from __future__ import annotations

from tigrcorn.protocols.http3.codec import SETTING_ENABLE_WEBTRANSPORT, SETTING_WT_MAX_SESSIONS
from tigrcorn.webtransport.wire import (
    Carrier,
    ConnectRequest,
    SETTING_ENABLE_WEBTRANSPORT_LEGACY,
    SETTING_WT_INITIAL_MAX_DATA,
    SETTING_WT_INITIAL_MAX_STREAMS_BIDI,
    SETTING_WT_INITIAL_MAX_STREAMS_UNI,
    WebTransportInit,
    WebTransportWireRuntime,
    h3_compat_settings,
    h3_draft13_settings,
    h3_draft13_transport_capable,
)


def test_webtransport_h3_draft13_settings_wt_max_sessions() -> None:
    settings = h3_draft13_settings(8)

    assert settings[SETTING_WT_MAX_SESSIONS] == 8
    assert h3_draft13_transport_capable(settings)


def test_webtransport_h3_draft13_initial_flow_settings_are_canonical() -> None:
    init = WebTransportInit(max_data=4096, max_streams_uni=2, max_streams_bidi=3)
    settings = h3_draft13_settings(8, init=init)

    assert settings[SETTING_WT_INITIAL_MAX_DATA] == 4096
    assert settings[SETTING_WT_INITIAL_MAX_STREAMS_UNI] == 2
    assert settings[SETTING_WT_INITIAL_MAX_STREAMS_BIDI] == 3


def test_webtransport_h3_draft13_accept_applies_initial_flow_settings() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    settings = h3_draft13_settings(
        1,
        init=WebTransportInit(max_data=128, max_streams_uni=1, max_streams_bidi=2),
    )

    decision = runtime.accept(
        ConnectRequest(
            stream_id=4,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H3,
            negotiated_settings=settings,
        )
    )

    assert decision.accepted
    assert runtime.sessions["4"].flow.max_data == 128
    assert runtime.sessions["4"].flow.max_streams_uni == 1
    assert runtime.sessions["4"].flow.max_streams_bidi == 2


def test_webtransport_h3_legacy_enable_webtransport_not_canonical() -> None:
    canonical = h3_draft13_settings(8)
    compat = h3_compat_settings(8)

    assert SETTING_ENABLE_WEBTRANSPORT == SETTING_ENABLE_WEBTRANSPORT_LEGACY
    assert SETTING_ENABLE_WEBTRANSPORT_LEGACY not in canonical
    assert compat[SETTING_ENABLE_WEBTRANSPORT_LEGACY] == 1
