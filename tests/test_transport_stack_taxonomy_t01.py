import pytest

from tigrcorn.transport_stacks import (
    ACTIVE_DRAFT,
    H2_WS,
    H2_WT,
    H3_WS,
    H3_WT,
    H3_WT_WS,
    STABLE_RFC,
    RuntimeStackError,
    classify_runtime_stack,
    compose_h3_listener_carriers,
    require_runtime_stack,
    requires_runtime_capability_gate,
)


def test_classifies_runtime_carriers_and_maturity():
    assert classify_runtime_stack(H2_WS).maturity == STABLE_RFC
    assert classify_runtime_stack(H3_WS).source == "RFC 9220"
    assert classify_runtime_stack(H3_WT).maturity == ACTIVE_DRAFT
    assert classify_runtime_stack(H2_WT).carrier == "webtransport-http2"


def test_draft_webtransport_carriers_require_runtime_gate():
    assert requires_runtime_capability_gate(H3_WT) is True
    assert requires_runtime_capability_gate(H2_WT) is True
    assert requires_runtime_capability_gate(H3_WS) is False
    with pytest.raises(RuntimeStackError):
        require_runtime_stack(H3_WT, allow_draft=False)


def test_invalid_nested_h3_webtransport_websocket_stack_fails_closed():
    assert classify_runtime_stack(H3_WT_WS).valid is False
    with pytest.raises(RuntimeStackError):
        require_runtime_stack(H3_WT_WS)


def test_h3_listener_composition_keeps_webtransport_and_websocket_separate():
    assert compose_h3_listener_carriers("h3", H3_WT, H3_WS) == ("h3", H3_WT, H3_WS)
    with pytest.raises(RuntimeStackError):
        compose_h3_listener_carriers(H3_WT_WS)
