from __future__ import annotations

from tests.support.client_session_matrix import ClientSessionTopologyHarness
from tigrcorn.contract import datagram_identity, stream_identity
from tigrcorn_protocols.client_session_coverage import ClientTopology, ProtocolCarrier, SessionScope


def test_webtransport_sessions_streams_and_datagrams_do_not_collapse() -> None:
    harness = ClientSessionTopologyHarness(
        ProtocolCarrier.WEBTRANSPORT_H3_QUIC,
        SessionScope.WEBTRANSPORT_SESSION_SCOPED,
    )
    topology = ClientTopology.CONCURRENT_CLIENTS
    stream_a = stream_identity("webtransport-stream", "wt-conn-a", "stream-a", session_id="wt-session-a")
    stream_b = stream_identity("webtransport-stream", "wt-conn-b", "stream-b", session_id="wt-session-b")
    datagram_a = datagram_identity("wt-conn-a", "datagram-a", session_id="wt-session-a")
    datagram_b = datagram_identity("wt-conn-b", "datagram-b", session_id="wt-session-b")

    harness.open("client-a", "wt-conn-a", "wt-session-a", topology)
    harness.open("client-b", "wt-conn-b", "wt-session-b", topology)
    harness.send(
        "client-a",
        "wt-conn-a",
        "wt-session-a",
        topology,
        "a-1",
        stream_id=stream_a.as_dict()["stream_id"],
        datagram_id=datagram_a.as_dict()["datagram_id"],
    )
    harness.send(
        "client-b",
        "wt-conn-b",
        "wt-session-b",
        topology,
        "b-1",
        stream_id=stream_b.as_dict()["stream_id"],
        datagram_id=datagram_b.as_dict()["datagram_id"],
    )

    sends = [event for event in harness.events if event["subevent"] == "send"]
    assert [(event["session_id"], event["stream_id"], event["datagram_id"]) for event in sends] == [
        ("wt-session-a", "stream-a", "datagram-a"),
        ("wt-session-b", "stream-b", "datagram-b"),
    ]
