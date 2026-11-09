from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tigrcorn_core.errors import ProtocolError

try:  # pragma: no cover - covered when the newer contract package is installed.
    from tigr_asgi_contract import semantic_domain as _contract_semantic_domain
    from tigr_asgi_contract import semantic_transition_target as _contract_transition_target
    from tigr_asgi_contract import validate_semantic_transition as _contract_validate_transition
except Exception:  # pragma: no cover - published contract fallback.
    _contract_semantic_domain = None
    _contract_transition_target = None
    _contract_validate_transition = None


_FALLBACK_TRANSITIONS = {
    ("completion", "accepted_by_runtime", "completion.queued"): "queued_for_transport",
    ("completion", "queued_for_transport", "completion.flushed"): "flushed_to_transport",
    ("completion", "flushed_to_transport", "completion.peer_acknowledged"): "peer_acknowledged",
    ("completion", "accepted_by_runtime", "completion.failed"): "failed_during_emit",
    ("completion", "queued_for_transport", "completion.failed"): "failed_during_emit",
    ("completion", "flushed_to_transport", "completion.failed"): "failed_during_emit",
    ("completion", "accepted_by_runtime", "completion.peer_aborted"): "aborted_by_peer",
    ("completion", "queued_for_transport", "completion.peer_aborted"): "aborted_by_peer",
    ("completion", "flushed_to_transport", "completion.peer_aborted"): "aborted_by_peer",
    ("backpressure", "writable", "backpressure.congested"): "congested",
    ("backpressure", "congested", "backpressure.saturated"): "saturated",
    ("backpressure", "saturated", "backpressure.draining"): "draining",
    ("backpressure", "draining", "backpressure.resumed"): "resumed",
    ("backpressure", "resumed", "backpressure.writable"): "writable",
    ("backpressure", "congested", "backpressure.resumed"): "resumed",
    ("cancellation", "requested", "cancellation.propagated"): "propagated",
    ("cancellation", "propagated", "cancellation.acknowledged"): "acknowledged",
    ("cancellation", "acknowledged", "cancellation.completed"): "completed",
    ("cancellation", "requested", "cancellation.ignored"): "ignored",
    ("cancellation", "propagated", "cancellation.failed"): "failed",
    ("cancellation", "acknowledged", "cancellation.failed"): "failed",
    ("disconnect", "graceful", "disconnect.peer_reset"): "peer_reset",
    ("disconnect", "graceful", "disconnect.transport_lost"): "transport_lost",
    ("disconnect", "graceful", "disconnect.timeout"): "timeout",
    ("disconnect", "graceful", "disconnect.protocol_error"): "protocol_error",
    ("disconnect", "graceful", "disconnect.server_shutdown"): "server_shutdown",
    ("channel_lifecycle", "initialized", "channel.opening"): "opening",
    ("channel_lifecycle", "opening", "channel.opened"): "open",
    ("channel_lifecycle", "open", "channel.read_closed"): "read_closed",
    ("channel_lifecycle", "open", "channel.write_closed"): "write_closed",
    ("channel_lifecycle", "open", "channel.closing"): "closing",
    ("channel_lifecycle", "open", "channel.closed"): "closed",
    ("channel_lifecycle", "open", "channel.failed"): "failed",
    ("channel_lifecycle", "open", "channel.lost"): "lost",
    ("channel_lifecycle", "read_closed", "channel.write_closed"): "closed",
    ("channel_lifecycle", "read_closed", "channel.closing"): "closing",
    ("channel_lifecycle", "read_closed", "channel.failed"): "failed",
    ("channel_lifecycle", "read_closed", "channel.lost"): "lost",
    ("channel_lifecycle", "write_closed", "channel.read_closed"): "closed",
    ("channel_lifecycle", "write_closed", "channel.closing"): "closing",
    ("channel_lifecycle", "write_closed", "channel.failed"): "failed",
    ("channel_lifecycle", "write_closed", "channel.lost"): "lost",
    ("channel_lifecycle", "closing", "channel.closed"): "closed",
    ("channel_lifecycle", "closing", "channel.failed"): "failed",
    ("channel_lifecycle", "closing", "channel.lost"): "lost",
}

_FALLBACK_CHANNEL_CAPABILITIES = {
    "initialized": {"can_drain": False, "can_read": False, "can_write": False, "terminal": False},
    "opening": {"can_drain": False, "can_read": False, "can_write": False, "terminal": False},
    "open": {"can_drain": False, "can_read": True, "can_write": True, "terminal": False},
    "read_closed": {"can_drain": True, "can_read": False, "can_write": True, "terminal": False},
    "write_closed": {"can_drain": True, "can_read": True, "can_write": False, "terminal": False},
    "closing": {"can_drain": True, "can_read": False, "can_write": False, "terminal": False},
    "closed": {"can_drain": False, "can_read": False, "can_write": False, "terminal": True},
    "failed": {"can_drain": False, "can_read": False, "can_write": False, "terminal": True},
    "lost": {"can_drain": False, "can_read": False, "can_write": False, "terminal": True},
}

_DISCONNECT_CAUSE_EVENTS = {
    "http.disconnect": "disconnect.peer_reset",
    "websocket.close": "disconnect.peer_reset",
    "websocket.disconnect": "disconnect.peer_reset",
    "http2.rst_stream": "disconnect.peer_reset",
    "http3.stream.reset": "disconnect.peer_reset",
    "quic.stop_sending": "disconnect.peer_reset",
    "quic.reset_stream": "disconnect.peer_reset",
    "webtransport.close": "disconnect.peer_reset",
    "webtransport.disconnect": "disconnect.peer_reset",
    "transport.lost": "disconnect.transport_lost",
    "tls.protocol_failure": "disconnect.protocol_error",
    "protocol.error": "disconnect.protocol_error",
    "timeout": "disconnect.timeout",
    "server.shutdown": "disconnect.server_shutdown",
    "worker.draining": "disconnect.server_shutdown",
}

_CANCELLATION_CAUSE_EVENTS = {
    "client_disconnected": "cancellation.propagated",
    "stream_reset": "cancellation.propagated",
    "server_shutdown": "cancellation.propagated",
    "timeout": "cancellation.propagated",
    "worker_draining": "cancellation.propagated",
}

_CHANNEL_CAUSE_EVENTS = {
    "open_requested": "channel.opening",
    "opened": "channel.opened",
    "h2.end_stream_received": "channel.read_closed",
    "h2.end_stream_sent": "channel.write_closed",
    "h2.half_closed_remote": "channel.read_closed",
    "h2.half_closed_local": "channel.write_closed",
    "h2.rst_stream": "channel.lost",
    "h2.goaway": "channel.closing",
    "h3.request_receive_closed": "channel.read_closed",
    "h3.request_send_closed": "channel.write_closed",
    "h3.request_cancelled": "channel.lost",
    "h3.request_rejected": "channel.failed",
    "h3.goaway": "channel.closing",
    "h3.stream_error": "channel.failed",
    "quic.receive_stream_closed": "channel.read_closed",
    "quic.send_stream_closed": "channel.write_closed",
    "quic.connection_close": "channel.closing",
    "quic.draining": "channel.closing",
    "quic.idle_timeout": "channel.lost",
    "websocket.closing": "channel.closing",
    "websocket.closed": "channel.closed",
    "websocket.http2.tunnel_ended": "channel.closing",
    "websocket.http3.tunnel_ended": "channel.closing",
    "tcp.reset": "channel.lost",
    "transport.lost": "channel.lost",
    "protocol.error": "channel.failed",
}

_DIRECTIONAL_RESET_EVENTS = {
    "h3.reset_stream",
    "quic.reset_stream",
}

_DIRECTIONAL_STOP_EVENTS = {
    "h3.stop_sending",
    "quic.stop_sending",
}


@dataclass(frozen=True, slots=True)
class SemanticObservation:
    domain: str
    previous_state: str
    event: str
    state: str
    source: str
    detail: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {
            "domain": self.domain,
            "event": self.event,
            "previous_state": self.previous_state,
            "source": self.source,
            "state": self.state,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


def enforce_semantic_transition(
    domain: str,
    state: str,
    event: str,
    *,
    source: str = "tigrcorn",
    detail: str | None = None,
) -> SemanticObservation:
    next_state = _semantic_transition_target(domain, state, event)
    return SemanticObservation(
        domain=domain,
        previous_state=state,
        event=event,
        state=next_state,
        source=source,
        detail=detail,
    )


def observe_completion(
    state: str,
    *,
    queued: bool = False,
    flushed: bool = False,
    peer_acknowledged: bool = False,
    failed: bool = False,
    peer_aborted: bool = False,
) -> SemanticObservation:
    event = _single_event(
        "completion",
        {
            "completion.queued": queued,
            "completion.flushed": flushed,
            "completion.peer_acknowledged": peer_acknowledged,
            "completion.failed": failed,
            "completion.peer_aborted": peer_aborted,
        },
    )
    return enforce_semantic_transition("completion", state, event)


def observe_backpressure(
    state: str,
    *,
    queued_bytes: int,
    high_watermark: int,
    resume_watermark: int | None = None,
) -> SemanticObservation:
    if queued_bytes < 0 or high_watermark < 0:
        raise ProtocolError("backpressure counters must be non-negative")
    if resume_watermark is not None and resume_watermark < 0:
        raise ProtocolError("resume watermark must be non-negative")
    if state == "writable" and queued_bytes >= high_watermark:
        event = "backpressure.congested"
    elif state == "congested" and queued_bytes >= high_watermark:
        event = "backpressure.saturated"
    elif state == "saturated":
        event = "backpressure.draining"
    elif state in {"congested", "draining"} and resume_watermark is not None and queued_bytes <= resume_watermark:
        event = "backpressure.resumed"
    elif state == "resumed":
        event = "backpressure.writable"
    else:
        raise ProtocolError(f"no backpressure semantic transition for state {state!r}")
    return enforce_semantic_transition("backpressure", state, event)


def observe_disconnect(state: str, cause: str) -> SemanticObservation:
    try:
        event = _DISCONNECT_CAUSE_EVENTS[cause]
    except KeyError as exc:
        raise ProtocolError(f"unsupported disconnect cause: {cause!r}") from exc
    return enforce_semantic_transition("disconnect", state, event)


def observe_transport_cancellation(state: str, cause: str) -> SemanticObservation:
    try:
        event = _CANCELLATION_CAUSE_EVENTS[cause]
    except KeyError as exc:
        raise ProtocolError(f"unsupported transport cancellation cause: {cause!r}") from exc
    return enforce_semantic_transition(
        "cancellation",
        state,
        event,
        detail=f"transport:{cause}",
    )


def observe_channel_lifecycle(
    state: str,
    cause: str,
    *,
    direction: str | None = None,
) -> SemanticObservation:
    event = _channel_event_for_cause(cause, direction=direction)
    return enforce_semantic_transition(
        "channel_lifecycle",
        state,
        event,
        detail=_channel_detail(cause, direction),
    )


def channel_lifecycle_capabilities(state: str) -> dict[str, bool]:
    effects = _channel_capability_effects()
    try:
        return dict(effects[state])
    except KeyError as exc:
        raise ProtocolError(f"unknown channel lifecycle state: {state!r}") from exc


def require_channel_readable(state: str) -> None:
    if not channel_lifecycle_capabilities(state)["can_read"]:
        raise ProtocolError(f"channel is not readable in lifecycle state {state!r}")


def require_channel_writable(state: str) -> None:
    if not channel_lifecycle_capabilities(state)["can_write"]:
        raise ProtocolError(f"channel is not writable in lifecycle state {state!r}")


def _single_event(domain: str, flags: Mapping[str, bool]) -> str:
    events = [event for event, active in flags.items() if active]
    if len(events) != 1:
        raise ProtocolError(f"{domain} observation must select exactly one semantic event")
    return events[0]


def _semantic_transition_target(domain: str, state: str, event: str) -> str:
    if _contract_transition_target is not None and _contract_validate_transition is not None:
        try:
            if _contract_validate_transition(domain, state, event):
                return str(_contract_transition_target(domain, state, event))
        except Exception:
            pass
    try:
        return _FALLBACK_TRANSITIONS[(domain, state, event)]
    except KeyError as exc:
        raise ProtocolError(f"illegal semantic transition for {domain}: {state} + {event}") from exc


def _channel_event_for_cause(cause: str, *, direction: str | None) -> str:
    if cause in _DIRECTIONAL_RESET_EVENTS or cause in _DIRECTIONAL_STOP_EVENTS:
        if direction in {"inbound", "read", "remote"}:
            return "channel.read_closed"
        if direction in {"outbound", "write", "local"}:
            return "channel.write_closed"
        raise ProtocolError(f"{cause} requires inbound/read or outbound/write direction")
    try:
        return _CHANNEL_CAUSE_EVENTS[cause]
    except KeyError as exc:
        raise ProtocolError(f"unsupported channel lifecycle cause: {cause!r}") from exc


def _channel_detail(cause: str, direction: str | None) -> str:
    if direction is None:
        return f"transport:{cause}"
    return f"transport:{cause}:{direction}"


def _channel_capability_effects() -> Mapping[str, Mapping[str, bool]]:
    if _contract_semantic_domain is not None:
        try:
            effects = _contract_semantic_domain("channel_lifecycle").get("capability_effects", {})
            if effects:
                return effects
        except Exception:
            pass
    return _FALLBACK_CHANNEL_CAPABILITIES


__all__ = [
    "SemanticObservation",
    "channel_lifecycle_capabilities",
    "enforce_semantic_transition",
    "observe_backpressure",
    "observe_channel_lifecycle",
    "observe_completion",
    "observe_disconnect",
    "observe_transport_cancellation",
    "require_channel_readable",
    "require_channel_writable",
]
