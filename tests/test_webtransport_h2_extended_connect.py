from __future__ import annotations

from tigrcorn.webtransport.wire import Carrier, ConnectRequest, WebTransportWireRuntime, h2_webtransport_settings


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
        stream_id=7,
        headers=base,
        carrier=Carrier.H2,
        negotiated_settings=h2_webtransport_settings(2),
        allowed_origins=("https://app.example",),
    )


def test_webtransport_h2_extended_connect_admits_session() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)

    decision = runtime.accept(_request())

    assert decision.accepted is True
    assert runtime.sessions["7"].path == "/wt"
    assert runtime.sessions["7"].carrier is Carrier.H2


def test_webtransport_h2_origin_authority_path_validation() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)

    bad_origin = runtime.accept(_request(origin="https://evil.example"))
    bad_authority = runtime.accept(_request(**{":authority": ""}))
    bad_path = runtime.accept(_request(**{":path": "wt"}))

    assert bad_origin.status == 403
    assert bad_authority.status == 400
    assert bad_path.reason == "path"


def test_webtransport_h2_connect_stream_id_is_session_id() -> None:
    runtime = WebTransportWireRuntime(max_sessions=2)

    decision = runtime.accept(_request())

    assert decision.session_id == "7"
    assert runtime.sessions["7"].connect_stream_id == 7
