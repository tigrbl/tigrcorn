from __future__ import annotations

import asyncio

import pytest

from tests.support.client_session_matrix import ClientSessionTopologyHarness, bounded_interleaved_pair, sequential_pair
from tigrcorn_protocols.client_session_coverage import ClientTopology, ProtocolCarrier


def test_sequential_schedule_completes_a_before_b_without_leakage() -> None:
    harness = sequential_pair(ProtocolCarrier.HTTP1)
    assert [event["client_id"] for event in harness.events] == [
        "client-a",
        "client-a",
        "client-a",
        "client-b",
        "client-b",
        "client-b",
    ]
    assert harness.sessions["session-a"].payloads == ["a-1"]
    assert harness.sessions["session-b"].payloads == ["b-1"]


def test_bounded_interleaved_schedule_preserves_controlled_order() -> None:
    harness = bounded_interleaved_pair(ProtocolCarrier.HTTP2)
    sends = [event for event in harness.events if event["subevent"] == "send"]
    assert [(event["client_id"], event["payload"]) for event in sends] == [
        ("client-a", "a-1"),
        ("client-b", "b-1"),
        ("client-a", "a-2"),
        ("client-b", "b-2"),
    ]


async def _exercise_concurrent_schedule() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.WEBSOCKET_H1)
    topology = ClientTopology.CONCURRENT_CLIENTS
    for index in range(5):
        harness.open(f"client-{index}", f"conn-{index}", f"session-{index}", topology)

    await asyncio.gather(
        *[
            harness.send_async(
                f"client-{index}",
                f"conn-{index}",
                f"session-{index}",
                topology,
                f"payload-{index}",
                delay=0.001 * (index % 2),
            )
            for index in range(5)
        ]
    )

    for index in range(5):
        assert harness.sessions[f"session-{index}"].payloads == [f"payload-{index}"]


def test_concurrent_schedule_preserves_session_isolation() -> None:
    asyncio.run(_exercise_concurrent_schedule())


def test_churn_schedule_reconnects_without_disrupting_active_client() -> None:
    harness = ClientSessionTopologyHarness(ProtocolCarrier.WEBTRANSPORT_H3_QUIC)
    topology = ClientTopology.CHURN_CLIENTS
    harness.open("client-a", "conn-a-1", "session-a-1", topology)
    harness.open("client-b", "conn-b", "session-b", topology)
    harness.send("client-b", "conn-b", "session-b", topology, "b-before")
    harness.close("client-a", "conn-a-1", "session-a-1", topology)
    harness.open("client-a", "conn-a-2", "session-a-2", topology)
    harness.send("client-a", "conn-a-2", "session-a-2", topology, "a-reconnected")
    harness.send("client-b", "conn-b", "session-b", topology, "b-after")

    assert harness.sessions["session-a-1"].closed is True
    assert harness.sessions["session-a-2"].payloads == ["a-reconnected"]
    assert harness.sessions["session-b"].payloads == ["b-before", "b-after"]
    with pytest.raises(RuntimeError, match="post-close"):
        harness.send("client-a", "conn-a-1", "session-a-1", topology, "late")
