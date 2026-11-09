from __future__ import annotations

from tests.support.client_session_matrix import bounded_interleaved_pair
from tigrcorn_protocols.client_session_coverage import ProtocolCarrier, SessionScope


def test_websocket_clients_are_connection_scoped_when_interleaved() -> None:
    harness = bounded_interleaved_pair(ProtocolCarrier.WEBSOCKET_H1, SessionScope.WEBSOCKET_CONNECTION_SCOPED)
    sends = [event for event in harness.events if event["subevent"] == "send"]
    assert all(event["session_scope"] == "websocket_connection_scoped" for event in sends)
    assert [event["connection_id"] for event in sends] == ["conn-a", "conn-b", "conn-a", "conn-b"]
