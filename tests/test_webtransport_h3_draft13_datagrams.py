from __future__ import annotations

from tigrcorn.webtransport.wire import (
    Carrier,
    ConnectRequest,
    WebTransportWireRuntime,
    decode_h3_datagram_payload,
    encode_h3_datagram_payload,
    h3_draft13_settings,
)


def test_webtransport_h3_draft13_datagram_session_association() -> None:
    runtime = WebTransportWireRuntime(max_sessions=1)
    runtime.accept(
        ConnectRequest(
            stream_id=4,
            headers={":method": "CONNECT", ":protocol": "webtransport", ":scheme": "https", ":authority": "a", ":path": "/wt"},
            carrier=Carrier.H3,
            negotiated_settings=h3_draft13_settings(1),
        )
    )

    stream_id, payload = decode_h3_datagram_payload(encode_h3_datagram_payload(4, b"dgram"))
    runtime.receive_datagram(str(stream_id), payload)

    assert stream_id == 4
    assert runtime.sessions["4"].datagrams == [b"dgram"]
