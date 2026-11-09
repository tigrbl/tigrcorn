from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    Carrier,
    ConnectRequest,
    WebTransportWireError,
    WebTransportWireRuntime,
    encode_protocol_headers,
    h3_draft13_settings,
    parse_protocol_header,
    select_wt_protocol,
)


def _request(**headers: str) -> ConnectRequest:
    base = {
        ":method": "CONNECT",
        ":protocol": "webtransport",
        ":scheme": "https",
        ":authority": "server.example",
        ":path": "/wt",
        "origin": "https://app.example",
    }
    base.update(headers)
    return ConnectRequest(
        stream_id=4,
        headers=base,
        carrier="h3",  # type: ignore[arg-type]
        negotiated_settings=h3_draft13_settings(2),
        allowed_origins=("https://app.example",),
    )


def test_webtransport_h3_draft13_extended_connect_admits_session() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)
    request = _request()
    request = ConnectRequest(
        stream_id=request.stream_id,
        headers=request.headers,
        carrier=Carrier.H3,
        negotiated_settings=request.negotiated_settings,
        allowed_origins=request.allowed_origins,
    )

    decision = runtime.accept(request)

    assert decision.accepted is True
    assert runtime.sessions["4"].carrier is Carrier.H3


def test_webtransport_h3_draft13_origin_authority_path_validation() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)
    request = _request(origin="https://evil.example")
    request = ConnectRequest(4, request.headers, Carrier.H3, request.negotiated_settings, request.allowed_origins)

    assert runtime.accept(request).status == 403


def test_webtransport_h3_wt_available_protocols_request() -> None:
    headers = encode_protocol_headers(("chat", "binary"), "chat")

    assert parse_protocol_header(headers["WT-Available-Protocols"]) == ("chat", "binary")


def test_webtransport_h3_wt_protocol_response_selection() -> None:
    assert select_wt_protocol(("chat", "binary"), "binary") == "binary"
    assert encode_protocol_headers(("chat",), "chat")["WT-Protocol"] == "chat"


def test_webtransport_h3_wt_protocol_invalid_selection_rejected() -> None:
    with pytest.raises(WebTransportWireError, match="WT-Protocol"):
        select_wt_protocol(("chat",), "video")
