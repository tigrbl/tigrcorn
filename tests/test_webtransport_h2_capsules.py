from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    CAPSULE_DATAGRAM,
    CAPSULE_WT_RESET_STREAM,
    CAPSULE_WT_STOP_SENDING,
    Capsule,
    Carrier,
    ConnectRequest,
    StreamDirection,
    WebTransportWireError,
    WebTransportWireRuntime,
    decode_capsule,
    decode_stream_capsule_payload,
    encode_capsule,
    encode_stream_capsule,
    encode_stream_error_payload,
    h2_webtransport_settings,
    parse_capsules,
)


def _runtime() -> WebTransportWireRuntime:
    runtime = WebTransportWireRuntime(max_sessions=2, max_datagram_size=32)
    decision = runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={
                ":method": "CONNECT",
                ":protocol": "webtransport",
                ":scheme": "https",
                ":authority": "server.example",
                ":path": "/wt",
            },
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(2),
        )
    )
    assert decision.accepted
    return runtime


def test_webtransport_h2_capsule_codec_roundtrip() -> None:
    raw = encode_capsule(CAPSULE_DATAGRAM, b"payload")

    capsule, offset = decode_capsule(raw)

    assert offset == len(raw)
    assert capsule == Capsule(CAPSULE_DATAGRAM, b"payload")
    assert parse_capsules(raw + raw) == (capsule, capsule)


def test_webtransport_h2_malformed_capsule_fail_closed() -> None:
    with pytest.raises(WebTransportWireError, match="truncated capsule"):
        decode_capsule(b"\x00\x05abc")


def test_webtransport_h2_bidi_stream_capsule_roundtrip() -> None:
    capsule = encode_stream_capsule(1, b"hello")
    stream_id, payload = decode_stream_capsule_payload(capsule.payload)

    runtime = _runtime()
    event = runtime.apply_capsule("3", capsule)

    assert (stream_id, payload) == (1, b"hello")
    assert event["event"] == "webtransport.stream"
    assert runtime.sessions["3"].streams[1] is StreamDirection.BIDI


def test_webtransport_h2_unidi_stream_capsule_roundtrip() -> None:
    runtime = _runtime()

    runtime.open_stream("3", 2, StreamDirection.UNI)
    runtime.receive_stream_data("3", 2, b"hello", StreamDirection.UNI)

    assert runtime.sessions["3"].streams[2] is StreamDirection.UNI
    assert runtime.sessions["3"].flow.stream_data_sent[2] == 5


def test_webtransport_h2_reset_stop_sending_capsules() -> None:
    runtime = _runtime()
    runtime.open_stream("3", 1, StreamDirection.BIDI)

    reset = Capsule(CAPSULE_WT_RESET_STREAM, encode_stream_error_payload(1, 42))
    stop = Capsule(CAPSULE_WT_STOP_SENDING, encode_stream_error_payload(1, 43))

    assert runtime.apply_capsule("3", reset)["error_code"] == 42
    assert runtime.apply_capsule("3", stop)["error_code"] == 43
    assert 1 not in runtime.sessions["3"].streams


def test_webtransport_h2_cross_session_stream_rejected() -> None:
    runtime = _runtime()

    with pytest.raises(WebTransportWireError, match="WT_SESSION_GONE"):
        runtime.receive_stream_data("999", 1, b"x", StreamDirection.BIDI)


def test_webtransport_h2_datagram_capsule_roundtrip() -> None:
    runtime = _runtime()

    event = runtime.apply_capsule("3", Capsule(CAPSULE_DATAGRAM, b"dgram"))

    assert event == {"event": "webtransport.datagram", "bytes": 5}
    assert runtime.sessions["3"].datagrams == [b"dgram"]


def test_webtransport_h2_datagram_budget_and_orphan_rejection() -> None:
    runtime = _runtime()

    with pytest.raises(WebTransportWireError, match="datagram size exceeded"):
        runtime.apply_capsule("3", Capsule(CAPSULE_DATAGRAM, b"x" * 33))
    with pytest.raises(WebTransportWireError, match="WT_SESSION_GONE"):
        runtime.apply_capsule("999", Capsule(CAPSULE_DATAGRAM, b"x"))
