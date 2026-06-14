from __future__ import annotations

import pytest

from tigrcorn.contract import (
    CompletionLevel,
    emit_complete,
    enforce_semantic_transition,
    observe_completion,
    observe_contract_backpressure,
    observe_disconnect,
    observe_transport_cancellation,
)
from tigrcorn.errors import ProtocolError


def test_t0_completion_levels_match_contract_vocabulary() -> None:
    assert {item.value for item in CompletionLevel} == {
        "accepted_by_runtime",
        "queued_for_transport",
        "flushed_to_transport",
        "peer_acknowledged",
        "failed_during_emit",
        "aborted_by_peer",
    }
    assert emit_complete("unit-1", level="acknowledged")["level"] == "peer_acknowledged"


def test_t1_tigrcorn_enforces_observed_transport_semantic_transitions() -> None:
    queued = observe_completion("accepted_by_runtime", queued=True)
    flushed = observe_completion(queued.state, flushed=True)
    acked = observe_completion(flushed.state, peer_acknowledged=True)

    assert queued.as_dict()["event"] == "completion.queued"
    assert acked.state == "peer_acknowledged"
    assert observe_disconnect("graceful", "http2.rst_stream").state == "peer_reset"
    assert observe_transport_cancellation("requested", "server_shutdown").state == "propagated"


def test_t1_backpressure_observation_projects_queue_pressure() -> None:
    congested = observe_contract_backpressure(
        "writable",
        queued_bytes=4096,
        high_watermark=4096,
    )
    saturated = observe_contract_backpressure(
        congested.state,
        queued_bytes=8192,
        high_watermark=4096,
    )
    draining = observe_contract_backpressure(
        saturated.state,
        queued_bytes=8192,
        high_watermark=4096,
    )
    resumed = observe_contract_backpressure(
        draining.state,
        queued_bytes=512,
        high_watermark=4096,
        resume_watermark=1024,
    )

    assert (congested.state, saturated.state, draining.state, resumed.state) == (
        "congested",
        "saturated",
        "draining",
        "resumed",
    )


@pytest.mark.parametrize(
    ("domain", "state", "event"),
    [
        ("completion", "accepted_by_runtime", "disconnect.peer_reset"),
        ("backpressure", "writable", "completion.flushed"),
        ("disconnect", "peer_reset", "disconnect.timeout"),
    ],
)
def test_t2_tigrcorn_rejects_ad_hoc_or_terminal_semantic_meanings(
    domain: str,
    state: str,
    event: str,
) -> None:
    with pytest.raises(ProtocolError):
        enforce_semantic_transition(domain, state, event)


def test_t2_completion_observation_rejects_ambiguous_socket_facts() -> None:
    with pytest.raises(ProtocolError, match="exactly one"):
        observe_completion("accepted_by_runtime", queued=True, failed=True)
