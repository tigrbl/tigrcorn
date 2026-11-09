from __future__ import annotations

from tigrcorn.webtransport.wire import (
    Carrier,
    ConnectRequest,
    WebTransportWireRuntime,
    h2_transport_capable,
    h2_webtransport_settings,
)


def _headers() -> dict[str, str]:
    return {
        ":method": "CONNECT",
        ":protocol": "webtransport",
        ":scheme": "https",
        ":authority": "server.example",
        ":path": "/wt",
        "origin": "https://app.example",
    }


def test_webtransport_h2_settings_negotiation() -> None:
    settings = h2_webtransport_settings(4)
    runtime = WebTransportWireRuntime(max_sessions=4)

    decision = runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers=_headers(),
            carrier=Carrier.H2,
            negotiated_settings=settings,
            allowed_origins=("https://app.example",),
        )
    )

    assert h2_transport_capable(settings)
    assert decision.accepted is True
    assert decision.session_id == "3"


def test_webtransport_h2_missing_settings_fail_closed() -> None:
    runtime = WebTransportWireRuntime(max_sessions=4)

    decision = runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers=_headers(),
            carrier=Carrier.H2,
            negotiated_settings={},
        )
    )

    assert decision.accepted is False
    assert decision.status == 421
    assert decision.reason == "webtransport-h2-settings-not-negotiated"
