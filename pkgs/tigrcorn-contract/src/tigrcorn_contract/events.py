from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tigrcorn_core.errors import ProtocolError


class CompletionLevel(StrEnum):
    ACCEPTED_BY_RUNTIME = "accepted_by_runtime"
    FLUSHED_TO_TRANSPORT = "flushed_to_transport"


class CompletionStatus(StrEnum):
    OK = "ok"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EventOrderRule:
    required_first: str
    allowed_after_close: tuple[str, ...] = ()


def _event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, **payload}


def stream_receive(stream_id: str, data: bytes, *, more: bool = False) -> dict[str, Any]:
    return _event("transport.stream.receive", stream_id=stream_id, data=data, more=more)


def stream_send(stream_id: str, data: bytes, *, more: bool = False) -> dict[str, Any]:
    return _event("transport.stream.send", stream_id=stream_id, data=data, more=more)


def datagram_receive(datagram_id: str, data: bytes, *, flow_controlled: bool = False) -> dict[str, Any]:
    return _event("transport.datagram.receive", datagram_id=datagram_id, data=data, flow_controlled=flow_controlled)


def datagram_send(datagram_id: str, data: bytes, *, flow_controlled: bool = False) -> dict[str, Any]:
    return _event("transport.datagram.send", datagram_id=datagram_id, data=data, flow_controlled=flow_controlled)


def webtransport_connect(session_id: str) -> dict[str, Any]:
    return _event("webtransport.connect", session_id=session_id)


def webtransport_accept(session_id: str) -> dict[str, Any]:
    return _event("webtransport.accept", session_id=session_id)


def webtransport_disconnect(session_id: str, *, code: int = 0, reason: str = "") -> dict[str, Any]:
    return _event("webtransport.disconnect", session_id=session_id, code=code, reason=reason)


def webtransport_close(session_id: str, *, code: int = 0, reason: str = "") -> dict[str, Any]:
    return _event("webtransport.close", session_id=session_id, code=code, reason=reason)


def webtransport_stream_receive(session_id: str, stream_id: str, data: bytes, *, more: bool = False) -> dict[str, Any]:
    return _event("webtransport.stream.receive", session_id=session_id, stream_id=stream_id, data=data, more=more)


def webtransport_stream_send(session_id: str, stream_id: str, data: bytes, *, more: bool = False) -> dict[str, Any]:
    return _event("webtransport.stream.send", session_id=session_id, stream_id=stream_id, data=data, more=more)


def webtransport_datagram_receive(session_id: str, datagram_id: str, data: bytes) -> dict[str, Any]:
    return _event("webtransport.datagram.receive", session_id=session_id, datagram_id=datagram_id, data=data)


def webtransport_datagram_send(session_id: str, datagram_id: str, data: bytes) -> dict[str, Any]:
    return _event("webtransport.datagram.send", session_id=session_id, datagram_id=datagram_id, data=data)


def emit_complete(
    unit_id: str,
    *,
    level: str | CompletionLevel = CompletionLevel.FLUSHED_TO_TRANSPORT,
    status: str | CompletionStatus = CompletionStatus.OK,
    detail: str | None = None,
) -> dict[str, Any]:
    try:
        completion_level = CompletionLevel(_normalize_completion_level(str(level)))
    except ValueError as exc:
        raise ProtocolError(f"unsupported completion level: {level!r}") from exc
    try:
        completion_status = CompletionStatus(str(status))
    except ValueError as exc:
        raise ProtocolError(f"unsupported completion status: {status!r}") from exc
    event = _event("transport.emit.complete", unit_id=unit_id, level=completion_level.value, status=completion_status.value)
    if detail:
        event["detail"] = detail
    return event


def _normalize_completion_level(level: str) -> str:
    aliases = {
        "buffered": CompletionLevel.ACCEPTED_BY_RUNTIME.value,
        "accepted": CompletionLevel.ACCEPTED_BY_RUNTIME.value,
        "flushed": CompletionLevel.FLUSHED_TO_TRANSPORT.value,
        "transport": CompletionLevel.FLUSHED_TO_TRANSPORT.value,
        "acknowledged": CompletionLevel.FLUSHED_TO_TRANSPORT.value,
    }
    return aliases.get(level, level)


def validate_event_order(events: list[dict[str, Any]], *, required_first: str, terminal_prefixes: tuple[str, ...]) -> None:
    if not events:
        raise ProtocolError("contract event sequence is empty")
    if events[0].get("type") != required_first:
        raise ProtocolError(f"first contract event must be {required_first}")
    closed = False
    for event in events:
        event_type = str(event.get("type", ""))
        if closed:
            raise ProtocolError("contract event emitted after terminal event")
        if event_type.startswith(terminal_prefixes):
            closed = True
