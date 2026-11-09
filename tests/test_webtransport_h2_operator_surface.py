from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import Carrier, WebTransportWireError, carrier_for_selection


def test_webtransport_h2_carrier_selection_cli_config() -> None:
    assert carrier_for_selection("tcp", "webtransport-h2") is Carrier.H2
    assert carrier_for_selection("tls", "webtransport_http2") is Carrier.H2


def test_webtransport_h2_not_selected_by_websocket_extended_connect() -> None:
    with pytest.raises(WebTransportWireError, match="HTTP/3 requires a UDP listener"):
        carrier_for_selection("tcp", "webtransport")
    with pytest.raises(WebTransportWireError, match="unsupported WebTransport"):
        carrier_for_selection("tcp", "websocket")
