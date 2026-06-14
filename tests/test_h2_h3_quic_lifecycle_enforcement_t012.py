from __future__ import annotations

import pytest

from tigrcorn.contract import (
    channel_lifecycle_capabilities,
    observe_channel_lifecycle,
    require_channel_readable,
    require_channel_writable,
)
from tigrcorn.errors import ProtocolError


def test_t0_h2_rfc9113_stream_lifecycle_projects_to_contract_states() -> None:
    assert observe_channel_lifecycle("open", "h2.end_stream_received").state == "read_closed"
    assert observe_channel_lifecycle("open", "h2.end_stream_sent").state == "write_closed"
    assert observe_channel_lifecycle("open", "h2.rst_stream").state == "lost"
    assert observe_channel_lifecycle("open", "h2.goaway").state == "closing"


def test_t1_h2_half_closed_remote_and_local_enforce_directional_io() -> None:
    read_closed = observe_channel_lifecycle("open", "h2.half_closed_remote")
    write_closed = observe_channel_lifecycle("open", "h2.half_closed_local")

    require_channel_writable(read_closed.state)
    with pytest.raises(ProtocolError, match="not readable"):
        require_channel_readable(read_closed.state)

    require_channel_readable(write_closed.state)
    with pytest.raises(ProtocolError, match="not writable"):
        require_channel_writable(write_closed.state)


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("h3.request_receive_closed", "read_closed"),
        ("h3.request_send_closed", "write_closed"),
        ("h3.request_cancelled", "lost"),
        ("h3.request_rejected", "failed"),
        ("h3.goaway", "closing"),
        ("h3.stream_error", "failed"),
    ],
)
def test_t1_h3_rfc9114_request_and_shutdown_lifecycle_is_projected(
    cause: str,
    expected: str,
) -> None:
    assert observe_channel_lifecycle("open", cause).state == expected


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("quic.receive_stream_closed", "read_closed"),
        ("quic.send_stream_closed", "write_closed"),
        ("quic.connection_close", "closing"),
        ("quic.draining", "closing"),
        ("quic.idle_timeout", "lost"),
    ],
)
def test_t1_quic_rfc9000_stream_and_connection_lifecycle_is_projected(
    cause: str,
    expected: str,
) -> None:
    assert observe_channel_lifecycle("open", cause).state == expected


@pytest.mark.parametrize("cause", ["h3.reset_stream", "quic.reset_stream", "h3.stop_sending", "quic.stop_sending"])
def test_t2_h3_and_quic_reset_or_stop_sending_require_direction(cause: str) -> None:
    with pytest.raises(ProtocolError, match="requires"):
        observe_channel_lifecycle("open", cause)

    assert observe_channel_lifecycle("open", cause, direction="read").state == "read_closed"
    assert observe_channel_lifecycle("open", cause, direction="write").state == "write_closed"


def test_t2_connection_terminal_and_closing_states_block_new_io() -> None:
    closing = observe_channel_lifecycle("open", "quic.connection_close")
    lost = observe_channel_lifecycle("open", "h2.rst_stream")

    assert channel_lifecycle_capabilities(closing.state)["can_drain"] is True
    assert channel_lifecycle_capabilities(lost.state)["terminal"] is True
    for state in (closing.state, lost.state):
        with pytest.raises(ProtocolError, match="not readable"):
            require_channel_readable(state)
        with pytest.raises(ProtocolError, match="not writable"):
            require_channel_writable(state)


def test_t2_websocket_tunnel_lifecycle_uses_rfc8441_and_rfc9220_projection() -> None:
    assert observe_channel_lifecycle("open", "websocket.http2.tunnel_ended").state == "closing"
    assert observe_channel_lifecycle("open", "websocket.http3.tunnel_ended").state == "closing"
