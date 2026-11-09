from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_DATA_BLOCKED,
    CAPSULE_WT_MAX_DATA,
    CAPSULE_WT_MAX_STREAMS_BIDI,
    CAPSULE_WT_MAX_STREAM_DATA,
    CAPSULE_WT_STREAMS_BLOCKED_BIDI,
    Capsule,
    Carrier,
    ConnectRequest,
    StreamDirection,
    WebTransportInit,
    WebTransportWireError,
    WebTransportWireRuntime,
    encode_varints,
    h2_webtransport_settings,
)


def test_webtransport_h2_session_flow_control_capsules() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/"},
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(1),
        )
    )

    runtime.apply_capsule("3", Capsule(CAPSULE_WT_MAX_DATA, encode_varints(4)))

    runtime.receive_stream_data("3", 1, b"1234", StreamDirection.BIDI)
    with pytest.raises(WebTransportWireError, match="WT_MAX_DATA exceeded"):
        runtime.receive_stream_data("3", 1, b"5", StreamDirection.BIDI)


def test_webtransport_h2_stream_flow_control_capsules() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/"},
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(1),
        )
    )

    runtime.apply_capsule("3", Capsule(CAPSULE_WT_MAX_STREAM_DATA, encode_varints(1, 3)))

    runtime.receive_stream_data("3", 1, b"123", StreamDirection.UNI)
    with pytest.raises(WebTransportWireError, match="WT_MAX_STREAM_DATA exceeded"):
        runtime.receive_stream_data("3", 1, b"4", StreamDirection.UNI)


def test_webtransport_h2_webtransport_init_flow_limits() -> None:
    settings = h2_webtransport_settings(1, WebTransportInit(max_data=10, max_streams_bidi=1))
    request = ConnectRequest(
        stream_id=3,
        headers={
            ":method": "CONNECT",
            ":protocol": "webtransport",
            ":scheme": "https",
            ":authority": "a",
            ":path": "/",
            "webtransport-init": "d=20, sb=2",
        },
        carrier=Carrier.H2,
        negotiated_settings=settings,
    )
    runtime = WebTransportWireRuntime(max_sessions=1)

    runtime.accept(request)

    assert runtime.sessions["3"].flow.max_data == 20
    assert runtime.sessions["3"].flow.max_streams_bidi == 2


def test_webtransport_h2_flow_control_blocked_capsules() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/"},
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(1),
        )
    )

    assert runtime.apply_capsule("3", Capsule(CAPSULE_WT_DATA_BLOCKED, encode_varints(10)))["event"] == "webtransport.flow-control"
    assert runtime.apply_capsule("3", Capsule(CAPSULE_WT_MAX_STREAMS_BIDI, encode_varints(1)))["event"] == "webtransport.flow-control"
    assert runtime.apply_capsule("3", Capsule(CAPSULE_WT_STREAMS_BLOCKED_BIDI, encode_varints(1)))["event"] == "webtransport.flow-control"
