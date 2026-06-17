from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


STABLE_RFC = "stable-rfc"
ACTIVE_DRAFT = "active-draft"
INVALID_LOCAL = "invalid-local"

H11 = "h11"
H2 = "h2"
H3 = "h3"
H2_WS = "h2+ws"
H3_WS = "h3+ws"
H2_WT = "h2+wt"
H3_WT = "h3+wt"
H3_WT_WS = "h3+wt+ws"

_H3_RUNTIME_CARRIERS = frozenset({H3, H3_WS, H3_WT})


class RuntimeStackError(ValueError):
    """Raised when Tigrcorn cannot provision a requested transport stack."""


@dataclass(frozen=True)
class RuntimeStackSupport:
    stack: str
    valid: bool
    maturity: str
    carrier: str
    source: str
    requires_capability_gate: bool
    notes: tuple[str, ...] = ()

    @property
    def is_stable_rfc(self) -> bool:
        return self.valid and self.maturity == STABLE_RFC

    @property
    def is_active_draft(self) -> bool:
        return self.valid and self.maturity == ACTIVE_DRAFT


_RUNTIME_STACKS = {
    H11: RuntimeStackSupport(H11, True, STABLE_RFC, H11, "RFC 9112", False),
    H2: RuntimeStackSupport(H2, True, STABLE_RFC, H2, "RFC 9113", False),
    H3: RuntimeStackSupport(H3, True, STABLE_RFC, H3, "RFC 9114 over RFC 9000", False),
    H2_WS: RuntimeStackSupport(H2_WS, True, STABLE_RFC, "websocket-http2", "RFC 8441", False),
    H3_WS: RuntimeStackSupport(H3_WS, True, STABLE_RFC, "websocket-http3", "RFC 9220", False),
    H3_WT: RuntimeStackSupport(
        H3_WT,
        True,
        ACTIVE_DRAFT,
        "webtransport-http3",
        "draft-ietf-webtrans-http3-15",
        True,
        ("Gate draft WebTransport H3 behavior behind explicit runtime capability.",),
    ),
    H2_WT: RuntimeStackSupport(
        H2_WT,
        True,
        ACTIVE_DRAFT,
        "webtransport-http2",
        "draft-ietf-webtrans-http2-14",
        True,
        ("Gate draft WebTransport H2 fallback behavior behind explicit runtime capability.",),
    ),
    H3_WT_WS: RuntimeStackSupport(
        H3_WT_WS,
        False,
        INVALID_LOCAL,
        "invalid-nested-h3-carrier",
        "local taxonomy rejection",
        False,
        ("Provision H3 WebTransport and H3 WebSocket as separate listener carriers.",),
    ),
}

RUNTIME_STACK_SUPPORT = MappingProxyType(_RUNTIME_STACKS)


def normalize_runtime_stack(stack: str) -> str:
    if not isinstance(stack, str):
        raise RuntimeStackError("runtime stack must be a string")
    return stack.strip().lower().replace(" ", "")


def classify_runtime_stack(stack: str) -> RuntimeStackSupport:
    normalized = normalize_runtime_stack(stack)
    try:
        return RUNTIME_STACK_SUPPORT[normalized]
    except KeyError as exc:
        raise RuntimeStackError(f"unknown runtime stack: {stack!r}") from exc


def require_runtime_stack(stack: str, *, allow_draft: bool = True) -> RuntimeStackSupport:
    support = classify_runtime_stack(stack)
    if not support.valid:
        raise RuntimeStackError(f"invalid runtime stack: {support.stack}")
    if support.requires_capability_gate and not allow_draft:
        raise RuntimeStackError(f"runtime stack requires draft capability gate: {support.stack}")
    return support


def requires_runtime_capability_gate(stack: str) -> bool:
    return classify_runtime_stack(stack).requires_capability_gate


def compose_h3_listener_carriers(*stacks: str) -> tuple[str, ...]:
    normalized = tuple(normalize_runtime_stack(stack) for stack in stacks)
    if H3_WT_WS in normalized:
        raise RuntimeStackError("h3+wt+ws cannot be provisioned as one Tigrcorn listener carrier")
    unknown = tuple(stack for stack in normalized if stack not in _H3_RUNTIME_CARRIERS)
    if unknown:
        raise RuntimeStackError(f"not an H3 listener carrier: {unknown[0]}")
    if len(set(normalized)) != len(normalized):
        raise RuntimeStackError("duplicate H3 listener carriers are not allowed")
    return normalized
