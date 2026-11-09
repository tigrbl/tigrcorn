from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_CLOSE_SESSION,
    CAPSULE_WT_DRAIN_SESSION,
    Capsule,
    Carrier,
    ConnectRequest,
    WebTransportWireError,
    WebTransportWireRuntime,
    encode_close_session_payload,
    h3_draft13_settings,
)


def _request(stream_id: int) -> ConnectRequest:
    return ConnectRequest(
        stream_id=stream_id,
        headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
        carrier=Carrier.H3,
        negotiated_settings=h3_draft13_settings(2),
    )


def test_webtransport_h3_draft13_goaway_blocks_new_session() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)
    runtime.goaway(4)

    assert runtime.accept(_request(4)).accepted is True
    assert runtime.accept(_request(8)).reason == "goaway-limit"


def test_webtransport_h3_draft13_wt_drain_session_capsule() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(_request(4))

    runtime.apply_capsule("4", Capsule(CAPSULE_WT_DRAIN_SESSION, b""))

    assert runtime.sessions["4"].state.value == "draining"


def test_webtransport_h3_draft13_wt_close_session_capsule() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(_request(4))

    event = runtime.apply_capsule("4", Capsule(CAPSULE_WT_CLOSE_SESSION, encode_close_session_payload(99, "done")))

    assert event == {"event": "webtransport.close", "code": 99, "reason": "done"}
    assert runtime.sessions["4"].state.value == "closed"


def test_webtransport_h3_draft13_wt_session_gone_error() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)

    with pytest.raises(WebTransportWireError, match="WT_SESSION_GONE"):
        runtime.apply_capsule("4", Capsule(CAPSULE_WT_DRAIN_SESSION, b""))
