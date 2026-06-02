from __future__ import annotations

from tests.support.client_session_matrix import ClientSessionTopologyHarness
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn_protocols.client_session_coverage import ClientTopology, ProtocolCarrier, SessionScope


def test_http3_quic_concurrent_clients_preserve_connection_and_stream_identity() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.HTTP3_QUIC, SessionScope.H3_STREAM_SCOPED)
    topology = ClientTopology.CONCURRENT_CLIENTS
    core_a = HTTP3ConnectionCore()
    core_b = HTTP3ConnectionCore()

    harness.open("client-a", "quic-conn-a", "h3-session-a", topology)
    harness.open("client-b", "quic-conn-b", "h3-session-b", topology)
    harness.send("client-a", "quic-conn-a", "h3-session-a", topology, "a-1", stream_id=0)
    harness.send("client-b", "quic-conn-b", "h3-session-b", topology, "b-1", stream_id=4)

    assert core_a is not core_b
    sends = [event for event in harness.events if event["subevent"] == "send"]
    assert [event["connection_id"] for event in sends] == ["quic-conn-a", "quic-conn-b"]
    assert harness.sessions["h3-session-a"].payloads == ["a-1"]
    assert harness.sessions["h3-session-b"].payloads == ["b-1"]
