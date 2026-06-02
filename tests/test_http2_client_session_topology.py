from __future__ import annotations

from tests.support.client_session_matrix import ClientSessionTopologyHarness
from tigrcorn.protocols.http2.streams import H2StreamRegistry
from tigrcorn_protocols.client_session_coverage import ClientTopology, ProtocolCarrier, SessionScope


def test_http2_interleaved_clients_preserve_stream_local_identity() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.HTTP2, SessionScope.H2_STREAM_SCOPED)
    topology = ClientTopology.BOUNDED_INTERLEAVED_CLIENTS
    registry = H2StreamRegistry()

    stream_a = registry.activate_remote(1, send_window=65535, receive_window=65535)
    stream_b = registry.activate_remote(3, send_window=65535, receive_window=65535)
    harness.open("client-a", "h2-conn", "h2-session-a", topology)
    harness.open("client-b", "h2-conn", "h2-session-b", topology)
    harness.send("client-a", "h2-conn", "h2-session-a", topology, "a-1", stream_id=stream_a.stream_id)
    harness.send("client-b", "h2-conn", "h2-session-b", topology, "b-1", stream_id=stream_b.stream_id)

    sends = [event for event in harness.events if event["subevent"] == "send"]
    assert [event["stream_id"] for event in sends] == [1, 3]
    assert harness.sessions["h2-session-a"].payloads == ["a-1"]
    assert harness.sessions["h2-session-b"].payloads == ["b-1"]
