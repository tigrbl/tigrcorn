from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_WT_RESET_STREAM,
    CAPSULE_WT_STOP_SENDING,
    Capsule,
    Carrier,
    ConnectRequest,
    H3_ERROR_WT_APPLICATION_ERROR,
    StreamDirection,
    WebTransportWireError,
    WebTransportWireRuntime,
    decode_h3_bidi_prefix,
    decode_h3_unidi_prefix,
    encode_h3_bidi_prefix,
    encode_h3_unidi_prefix,
    encode_stream_error_payload,
    h3_draft13_settings,
)


def _runtime() -> WebTransportWireRuntime:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=4,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H3,
            negotiated_settings=h3_draft13_settings(1),
        )
    )
    return runtime


def test_webtransport_h3_draft13_bidi_stream_prefix() -> None:
    session_id, payload = decode_h3_bidi_prefix(encode_h3_bidi_prefix(4) + b"data")

    assert (session_id, payload) == (4, b"data")


def test_webtransport_h3_draft13_unidi_stream_type_and_session_id() -> None:
    session_id, payload = decode_h3_unidi_prefix(encode_h3_unidi_prefix(4) + b"data")

    assert (session_id, payload) == (4, b"data")


def test_webtransport_h3_draft13_unidi_orphan_session_rejected() -> None:
    runtime = _runtime()

    with pytest.raises(WebTransportWireError, match="WT_SESSION_GONE"):
        runtime.receive_stream_data("999", 10, b"x", StreamDirection.UNI)


def test_webtransport_h3_draft13_reset_stream_at() -> None:
    runtime = _runtime()
    runtime.open_stream("4", 8, StreamDirection.BIDI)

    event = runtime.apply_capsule("4", Capsule(CAPSULE_WT_RESET_STREAM, encode_stream_error_payload(8, 10)))

    assert event["stream_id"] == 8
    assert 8 not in runtime.sessions["4"].streams


def test_webtransport_h3_draft13_stop_sending_maps_to_contract_close() -> None:
    runtime = _runtime()
    runtime.open_stream("4", 8, StreamDirection.BIDI)

    event = runtime.apply_capsule("4", Capsule(CAPSULE_WT_STOP_SENDING, encode_stream_error_payload(8, 11)))

    assert event == {"event": "webtransport.stream.error", "stream_id": 8, "error_code": 11}


def test_webtransport_h3_draft13_application_error_range() -> None:
    assert H3_ERROR_WT_APPLICATION_ERROR == 0x52E4A40FA8DB
