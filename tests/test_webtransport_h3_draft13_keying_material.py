from __future__ import annotations

import pytest

from tigrcorn.webtransport.wire import (
    Carrier,
    ConnectRequest,
    WebTransportWireError,
    WebTransportWireRuntime,
    exporter_matches,
    h2_webtransport_settings,
    h3_draft13_settings,
)


def test_webtransport_h3_draft13_keying_material_exporter() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=4,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H3,
            negotiated_settings=h3_draft13_settings(1),
        )
    )

    left = runtime.keying_material_exporter("4", "EXPORTER-WebTransport", b"context", 16)
    right = runtime.keying_material_exporter("4", "EXPORTER-WebTransport", b"context", 16)

    assert len(left) == 16
    assert exporter_matches(left, right)


def test_webtransport_h3_draft13_exporter_unavailable_fail_closed() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=3,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H2,
            negotiated_settings=h2_webtransport_settings(1),
        )
    )

    with pytest.raises(WebTransportWireError, match="HTTP/3 over QUIC"):
        runtime.keying_material_exporter("3", "EXPORTER-WebTransport", b"context", 16)
