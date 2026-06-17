import pytest

from tigrcorn.transport_stacks import (
    H2_WS,
    H3_WS,
    H3_WT,
    H3_WT_WS,
    RUNTIME_STACK_SUPPORT,
    RuntimeStackError,
    classify_runtime_stack,
    compose_h3_listener_carriers,
    require_runtime_stack,
)


def test_runtime_stack_normalization_is_case_and_whitespace_tolerant():
    assert classify_runtime_stack(" H3 + WT ").stack == H3_WT
    assert classify_runtime_stack("H2+WS").stack == H2_WS


def test_unknown_and_non_string_runtime_stack_inputs_fail_closed():
    for stack in ("h4", "wt+ws", ""):
        with pytest.raises(RuntimeStackError):
            classify_runtime_stack(stack)
    with pytest.raises(RuntimeStackError):
        classify_runtime_stack(None)  # type: ignore[arg-type]


def test_runtime_stack_registry_view_is_immutable():
    with pytest.raises(TypeError):
        RUNTIME_STACK_SUPPORT["local"] = RUNTIME_STACK_SUPPORT[H3_WT]  # type: ignore[index]


def test_draft_gate_and_nested_stack_rejections_are_stable():
    with pytest.raises(RuntimeStackError):
        require_runtime_stack(" H3 + WT ", allow_draft=False)
    with pytest.raises(RuntimeStackError):
        require_runtime_stack(f" {H3_WT_WS.upper()} ")


def test_h3_listener_rejects_duplicate_and_non_h3_carriers():
    with pytest.raises(RuntimeStackError):
        compose_h3_listener_carriers(H3_WS, H3_WS)
    with pytest.raises(RuntimeStackError):
        compose_h3_listener_carriers(H3_WT, "h2+wt")
    assert compose_h3_listener_carriers(H3_WT, H3_WS) == (H3_WT, H3_WS)
