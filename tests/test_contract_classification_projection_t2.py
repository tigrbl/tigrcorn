from __future__ import annotations

from types import SimpleNamespace

import pytest

import tigrcorn_contract.projection as projection_module
from tigrcorn_contract import (
    project_receive_event,
    project_scope_classification,
    project_send_event,
    validate_projected_event,
    webtransport_datagram_send,
    webtransport_stream_receive,
    webtransport_stream_send,
)
from tigrcorn_core.errors import ProtocolError


def scope(scope_type: str, binding: str | None = None, **extra):
    transport = {} if binding is None else {"binding": binding}
    value = {"type": scope_type, "ext": {"transport": transport}, **extra}
    if scope_type == "webtransport":
        value["ext"]["webtransport"] = {
            "supports_bidi_streams": True,
            "supports_uni_streams": True,
            "supports_datagrams": True,
        }
    return value


def test_projection_rejects_explicit_unknown_binding_metadata():
    with pytest.raises(ProtocolError, match="unsupported binding"):
        project_scope_classification(scope("http", "http.unknown"))


def test_projection_rejects_non_mapping_transport_metadata():
    with pytest.raises(ProtocolError, match="scope ext must be a mapping"):
        project_scope_classification({"type": "http", "ext": "bad"})

    with pytest.raises(ProtocolError, match="scope ext.transport must be a mapping"):
        project_scope_classification({"type": "http", "ext": {"transport": "bad"}})


def test_projection_rejects_invalid_channel_and_event_pair():
    http_scope = scope("http", "http.rest")

    with pytest.raises(ProtocolError, match="unsupported ASGI contract channel"):
        validate_projected_event(http_scope, "egress", {"type": "http.request"})

    with pytest.raises(ProtocolError, match="no contract classification"):
        validate_projected_event(http_scope, "send", {"type": "http.request", "body": b"{}"})


def test_projection_rejects_unknown_and_illegal_framing_values():
    http_scope = scope("http", "http.rest")

    with pytest.raises(ProtocolError, match="unsupported framing"):
        project_receive_event(http_scope, {"type": "http.request", "body": b"{}", "framing": "yaml"})

    with pytest.raises(ProtocolError, match="illegal"):
        project_send_event(http_scope, {"type": "http.response.body", "body": b"data: x\n\n", "framing": "sse"})


def test_projection_rejects_jsonrpc_without_complete_document_metadata():
    jsonrpc_scope = scope("http", "http.jsonrpc")

    with pytest.raises(ProtocolError, match="jsonrpc_complete"):
        project_send_event(jsonrpc_scope, {"type": "http.response.body", "body": b"{}", "framing": "jsonrpc"})

    projected = project_send_event(
        jsonrpc_scope,
        {"type": "http.response.body", "body": b"{}", "framing": "jsonrpc", "jsonrpc_complete": True},
    )
    assert projected.allowed_framings == ("jsonrpc",)


def test_projection_rejects_ndjson_that_claims_jsonrpc_completeness():
    stream_scope = scope("http", "http.stream")

    with pytest.raises(ProtocolError, match="ndjson"):
        project_receive_event(
            stream_scope,
            {"type": "http.request", "body": b'{"id":1}\n', "framing": "ndjson", "jsonrpc_complete": True},
        )


def test_webtransport_capability_gates_fail_closed_when_missing_or_false():
    missing_capabilities = {"type": "webtransport", "ext": {"transport": {"binding": "webtransport"}}}

    with pytest.raises(ProtocolError, match="no contract classification"):
        project_receive_event(
            missing_capabilities,
            webtransport_stream_receive("s1", "st1", b"{}", stream_direction="bidi", framing="json"),
        )

    disabled_datagrams = scope("webtransport", "webtransport")
    disabled_datagrams["ext"]["webtransport"]["supports_datagrams"] = False

    with pytest.raises(ProtocolError, match="no contract classification"):
        project_send_event(disabled_datagrams, webtransport_datagram_send("s1", "d1", b"{}", framing="json"))


def test_webtransport_lane_metadata_is_required_and_directional():
    wt_scope = scope("webtransport", "webtransport")

    with pytest.raises(ProtocolError, match="stream_id"):
        project_receive_event(wt_scope, {"type": "webtransport.stream.receive", "stream_direction": "bidi", "data": b"x"})

    with pytest.raises(ProtocolError, match="stream_direction"):
        project_receive_event(wt_scope, {"type": "webtransport.stream.receive", "stream_id": "st1", "data": b"x"})

    with pytest.raises(ProtocolError, match="no contract classification"):
        project_receive_event(
            wt_scope,
            webtransport_stream_receive("s1", "st1", b"x", stream_direction="server_to_client"),
        )

    with pytest.raises(ProtocolError, match="no contract classification"):
        project_send_event(
            wt_scope,
            webtransport_stream_send("s1", "st2", b"x", stream_direction="client_to_server"),
        )


def test_webtransport_datagram_and_message_lane_fail_closed():
    wt_scope = scope("webtransport", "webtransport")

    with pytest.raises(ProtocolError, match="datagram_id"):
        project_send_event(wt_scope, {"type": "webtransport.datagram.send", "session_id": "s1", "data": b"x"})

    with pytest.raises(ProtocolError, match="illegal"):
        project_send_event(wt_scope, webtransport_datagram_send("s1", "d1", b"{}", framing="ndjson"))

    with pytest.raises(ProtocolError, match="no contract classification"):
        validate_projected_event(wt_scope, "receive", {"type": "webtransport.message.receive", "data": b"bad"})


def test_projection_rejects_subsurface_payload_field():
    with pytest.raises(ProtocolError, match="subsurface"):
        project_send_event(scope("websocket", "websocket"), {"type": "websocket.send", "text": "x", "subsurface": "ws.message"})


def test_contract_classifier_drift_fails_loudly(monkeypatch):
    def fake_classifier(_scope, _channel, _event_type, _event):
        return SimpleNamespace(
            event="http.request",
            channel="receive",
            scope_type="http",
            binding="rest",
            family="message",
            exchange="duplex",
            direction="client_to_server",
            allowed_framings=("json",),
        )

    monkeypatch.setattr(projection_module, "_contract_classify_event", fake_classifier)
    monkeypatch.setattr(projection_module, "_contract_validate_event_payload", None)

    with pytest.raises(ProtocolError, match="contract classification drift"):
        project_receive_event(scope("http", "http.rest"), {"type": "http.request", "body": b"{}", "framing": "json"})
