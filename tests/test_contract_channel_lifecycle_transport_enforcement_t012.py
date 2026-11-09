from __future__ import annotations

import pytest

from tigrcorn.contract import (
    channel_lifecycle_capabilities,
    observe_channel_lifecycle,
    require_channel_readable,
    require_channel_writable,
)
from tigrcorn.errors import ProtocolError


def test_t0_transport_protocol_facts_project_to_contract_lifecycle_vocabulary() -> None:
    opening = observe_channel_lifecycle("initialized", "open_requested")
    opened = observe_channel_lifecycle(opening.state, "opened")
    read_closed = observe_channel_lifecycle(opened.state, "h2.half_closed_remote")

    assert opening.as_dict()["event"] == "channel.opening"
    assert opened.state == "open"
    assert read_closed.as_dict() == {
        "detail": "transport:h2.half_closed_remote",
        "domain": "channel_lifecycle",
        "event": "channel.read_closed",
        "previous_state": "open",
        "source": "tigrcorn",
        "state": "read_closed",
    }


def test_t1_transport_lifecycle_enforces_read_and_write_capabilities() -> None:
    read_closed = observe_channel_lifecycle("open", "h2.half_closed_remote")
    write_closed = observe_channel_lifecycle("open", "h2.half_closed_local")

    assert channel_lifecycle_capabilities(read_closed.state)["can_write"] is True
    assert channel_lifecycle_capabilities(read_closed.state)["can_read"] is False
    require_channel_writable(read_closed.state)
    with pytest.raises(ProtocolError, match="not readable"):
        require_channel_readable(read_closed.state)

    assert channel_lifecycle_capabilities(write_closed.state)["can_read"] is True
    assert channel_lifecycle_capabilities(write_closed.state)["can_write"] is False
    require_channel_readable(write_closed.state)
    with pytest.raises(ProtocolError, match="not writable"):
        require_channel_writable(write_closed.state)


@pytest.mark.parametrize(
    ("cause", "direction", "expected"),
    [
        ("h3.reset_stream", "inbound", "read_closed"),
        ("h3.reset_stream", "outbound", "write_closed"),
        ("quic.reset_stream", "read", "read_closed"),
        ("quic.reset_stream", "write", "write_closed"),
        ("h3.stop_sending", "read", "read_closed"),
        ("h3.stop_sending", "write", "write_closed"),
        ("quic.stop_sending", "read", "read_closed"),
        ("quic.stop_sending", "write", "write_closed"),
    ],
)
def test_t2_h3_and_quic_lifecycle_events_preserve_directionality(
    cause: str,
    direction: str | None,
    expected: str,
) -> None:
    observation = observe_channel_lifecycle("open", cause, direction=direction)

    assert observation.state == expected


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("websocket.closing", "closing"),
        ("tcp.reset", "lost"),
        ("protocol.error", "failed"),
    ],
)
def test_t2_transport_faults_project_without_application_policy(
    cause: str,
    expected: str,
) -> None:
    observation = observe_channel_lifecycle("open", cause)

    assert observation.state == expected
    assert observation.domain == "channel_lifecycle"


def test_t2_directional_resets_require_direction_and_terminal_states_block_io() -> None:
    with pytest.raises(ProtocolError, match="requires"):
        observe_channel_lifecycle("open", "h3.reset_stream")
    with pytest.raises(ProtocolError, match="requires"):
        observe_channel_lifecycle("open", "quic.stop_sending")

    lost = observe_channel_lifecycle("open", "tcp.reset")
    assert channel_lifecycle_capabilities(lost.state)["terminal"] is True
    with pytest.raises(ProtocolError, match="not readable"):
        require_channel_readable(lost.state)
    with pytest.raises(ProtocolError, match="not writable"):
        require_channel_writable(lost.state)
