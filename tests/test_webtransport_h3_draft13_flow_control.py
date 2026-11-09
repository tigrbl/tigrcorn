from __future__ import annotations

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_DATA_BLOCKED,
    CAPSULE_WT_MAX_DATA,
    CAPSULE_WT_MAX_STREAMS_BIDI,
    CAPSULE_WT_STREAMS_BLOCKED_BIDI,
    Capsule,
    Carrier,
    ConnectRequest,
    WebTransportWireRuntime,
    encode_varints,
    h3_draft13_settings,
)


def _runtime() -> WebTransportWireRuntime:
    runtime = WebTransportWireRuntime(max_sessions=2)
    runtime.accept(
        ConnectRequest(
            stream_id=4,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H3,
            negotiated_settings=h3_draft13_settings(2),
        )
    )
    return runtime


def test_webtransport_h3_draft13_wt_max_streams_capsule() -> None:
    runtime = _runtime()

    runtime.apply_capsule("4", Capsule(CAPSULE_WT_MAX_STREAMS_BIDI, encode_varints(2)))

    assert runtime.sessions["4"].flow.max_streams_bidi == 2


def test_webtransport_h3_draft13_wt_streams_blocked_capsule() -> None:
    assert _runtime().apply_capsule("4", Capsule(CAPSULE_WT_STREAMS_BLOCKED_BIDI, encode_varints(2)))["event"] == "webtransport.flow-control"


def test_webtransport_h3_draft13_wt_max_data_capsule() -> None:
    runtime = _runtime()

    runtime.apply_capsule("4", Capsule(CAPSULE_WT_MAX_DATA, encode_varints(100)))

    assert runtime.sessions["4"].flow.max_data == 100


def test_webtransport_h3_draft13_wt_data_blocked_capsule() -> None:
    assert _runtime().apply_capsule("4", Capsule(CAPSULE_WT_DATA_BLOCKED, encode_varints(100)))["event"] == "webtransport.flow-control"
