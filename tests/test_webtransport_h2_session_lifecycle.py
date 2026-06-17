from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_CLOSE_SESSION,
    CAPSULE_WT_DRAIN_SESSION,
    Capsule,
    Carrier,
    ConnectRequest,
    StreamDirection,
    WebTransportWireError,
    WebTransportWireRuntime,
    encode_close_session_payload,
    h2_webtransport_settings,
)


def _runtime() -> WebTransportWireRuntime:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(1),
        )
    )
    return runtime


def test_webtransport_h2_connect_close_terminates_session() -> None:
    runtime = _runtime()

    runtime.apply_capsule("3", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(0, "done")))

    assert runtime.sessions["3"].state.value == "closed"
    assert runtime.sessions["3"].close_reason == "done"


def test_webtransport_h2_close_session_capsule() -> None:
    runtime = _runtime()

    event = runtime.apply_capsule("3", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(7, "bye")))

    assert event == {"event": "webtransport.close", "code": 7, "reason": "bye"}


def test_webtransport_h2_drain_session_capsule() -> None:
    runtime = _runtime()

    event = runtime.apply_capsule("3", Capsule(CAPSULE_WT_DRAIN_SESSION, b""))

    assert event == {"event": "webtransport.drain"}
    assert runtime.sessions["3"].state.value == "draining"


def test_webtransport_h2_post_close_traffic_rejected() -> None:
    runtime = _runtime()
    runtime.apply_capsule("3", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(0, "")))

    with pytest.raises(WebTransportWireError, match="closed"):
        runtime.receive_stream_data("3", 1, b"x", StreamDirection.BIDI)
