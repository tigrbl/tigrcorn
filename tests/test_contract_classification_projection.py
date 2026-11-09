from __future__ import annotations

import pytest

from tigrcorn_contract import (
    EventProjection,
    project_receive_event,
    project_scope_classification,
    project_send_event,
    validate_projected_event,
    websocket_receive,
    websocket_send,
    webtransport_datagram_receive,
    webtransport_datagram_send,
    webtransport_stream_receive,
    webtransport_stream_send,
)
from tigrcorn_core.errors import ProtocolError


def scope(scope_type: str, binding: str, **extra):
    value = {"type": scope_type, "ext": {"transport": {"binding": binding}}, **extra}
    if scope_type == "webtransport":
        value["ext"]["webtransport"] = {
            "supports_bidi_streams": True,
            "supports_uni_streams": True,
            "supports_datagrams": True,
        }
    return value


def test_projection_api_exports_scope_transport_metadata_without_subsurface():
    http_scope = {"type": "http", "http_version": "1.1", "scheme": "https", "ext": {"transport": {"binding": "http.rest"}}}

    projection = project_scope_classification(http_scope)

    assert projection.scope_type == "http"
    assert projection.binding == "rest"
    assert http_scope["ext"]["transport"]["binding"] == "rest"
    assert http_scope["ext"]["transport"]["alpn"] == "http/1.1"
    assert http_scope["ext"]["transport"]["secure"] is True
    assert "subsurface" not in http_scope


@pytest.mark.parametrize(
    ("case_scope", "channel", "event", "expected"),
    [
        (scope("http", "http.rest", http_version="1.1"), "receive", {"type": "http.request", "body": b"{}", "framing": "json"}, ("request", "unary", "client_to_server")),
        (scope("http", "http.jsonrpc"), "send", {"type": "http.response.body", "body": b"{}", "framing": "jsonrpc", "jsonrpc_complete": True}, ("request", "unary", "server_to_client")),
        (scope("http", "http.stream", http_version="2"), "receive", {"type": "http.request", "body": b"line\n", "framing": "ndjson"}, ("stream", "client_stream", "client_to_server")),
        (scope("http", "http.sse"), "send", {"type": "http.response.body", "body": b"data: x\n\n", "framing": "sse"}, ("stream", "server_stream", "server_to_client")),
        (scope("websocket", "websocket"), "receive", websocket_receive("ws-1", text="hello"), ("message", "duplex", "client_to_server")),
        (scope("websocket", "websocket"), "send", websocket_send("ws-1", bytes_=b"hello"), ("message", "duplex", "server_to_client")),
        (scope("webtransport", "webtransport"), "receive", {"type": "webtransport.connect", "session_id": "s1"}, ("session", "unary", "client_to_server")),
        (scope("webtransport", "webtransport"), "send", {"type": "webtransport.accept", "session_id": "s1"}, ("session", "unary", "server_to_client")),
        (scope("webtransport", "webtransport"), "receive", {**webtransport_stream_receive("s1", "st1", b"a", stream_direction="bidi", framing="jsonrpc"), "jsonrpc_complete": True}, ("stream", "duplex", "client_to_server")),
        (scope("webtransport", "webtransport"), "receive", webtransport_stream_receive("s1", "st2", b"a", stream_direction="client_to_server", framing="ndjson"), ("stream", "client_stream", "client_to_server")),
        (scope("webtransport", "webtransport"), "send", webtransport_stream_send("s1", "st3", b"a", stream_direction="server_to_client", framing="ndjson"), ("stream", "server_stream", "server_to_client")),
        (scope("webtransport", "webtransport"), "receive", webtransport_datagram_receive("s1", "d1", b"a", framing="json"), ("datagram", "duplex", "client_to_server")),
        (scope("webtransport", "webtransport"), "send", webtransport_datagram_send("s1", "d2", b"a", framing="binary"), ("datagram", "duplex", "server_to_client")),
    ],
)
def test_project_event_classification_valid_t1_cases(case_scope, channel, event, expected):
    projection = project_receive_event(case_scope, event) if channel == "receive" else project_send_event(case_scope, event)

    assert isinstance(projection, EventProjection)
    assert (projection.family, projection.exchange, projection.direction) == expected
    assert projection.event == event["type"]
    assert projection.channel == channel


def test_projection_rejects_subsurface_and_webtransport_message_family():
    wt_scope = scope("webtransport", "webtransport")

    with pytest.raises(ProtocolError):
        validate_projected_event(wt_scope, "receive", {"type": "webtransport.stream.receive", "stream_id": "st1", "subsurface": "wt.stream"})

    with pytest.raises(ProtocolError):
        validate_projected_event(wt_scope, "receive", {"type": "webtransport.message.receive", "data": b"bad"})


def test_projection_rejects_invalid_webtransport_lane_framing():
    wt_scope = scope("webtransport", "webtransport")

    with pytest.raises(ProtocolError):
        project_send_event(wt_scope, webtransport_datagram_send("s1", "d1", b"{}", framing="jsonrpc"))

    with pytest.raises(ProtocolError):
        project_send_event(wt_scope, webtransport_stream_send("s1", "st1", b"{}", stream_direction="client_to_server"))
