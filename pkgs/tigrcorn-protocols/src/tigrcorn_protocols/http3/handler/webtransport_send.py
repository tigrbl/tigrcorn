from __future__ import annotations

from typing import Any


async def send_message(owner: Any, message: dict[str, Any]) -> None:
    """Execute one serialized WebTransport ASGI send event."""
    try:
        await _send_message(owner, message)
    except Exception as exc:
        await _report_completion(owner, message, error=exc)
        raise
    else:
        await _report_completion(owner, message)


async def _report_completion(
    owner: Any,
    message: dict[str, Any],
    *,
    error: BaseException | None = None,
) -> None:
    emit_id = message.get("emit_id")
    if emit_id is None:
        return
    event = {
        "type": "transport.emit.failed" if error is not None else "transport.emit.complete",
        "emit_id": str(emit_id),
        "level": "failed_during_emit" if error is not None else "flushed_to_transport",
        "status": "failed" if error is not None else "ok",
        "session_id": owner.session_id,
    }
    for key in ("stream_id", "stream_direction", "datagram_id"):
        if message.get(key) is not None:
            event[key] = message[key]
    if error is not None:
        event.update(
            {
                "message": str(error),
                "failure_phase": "transport.emit",
                "retryable": not owner.closed,
            }
        )
    await owner.receive.put(event)


async def _send_message(owner: Any, message: dict[str, Any]) -> None:
    typ = message.get("type")
    owner._trace_webtransport(
        "webtransport.asgi.send",
        **owner._trace_session_fields(),
        stream_id=message.get("stream_id", owner.stream_id),
        session_id=owner.session_id,
        owner_stream_id=owner.stream_id,
        type=str(typ),
        bytes=(
            len(bytes(message.get("data", b"")))
            if message.get("data") is not None
            else None
        ),
    )
    if typ == "webtransport.accept":
        if owner.accepted:
            raise RuntimeError("webtransport.accept sent more than once")
        owner.accepted = True
        return
    if typ == "webtransport.stream.send":
        await _send_stream(owner, message)
        return
    if typ == "webtransport.stream.close":
        await _close_stream(owner, message)
        return
    if typ and str(typ).startswith("webtransport.message."):
        raise RuntimeError("webtransport message is not a native WebTransport lane")
    if typ == "webtransport.datagram.send":
        if not owner.accepted:
            raise RuntimeError("webtransport.datagram.send before webtransport.accept")
        await owner.handler._send_webtransport_datagram(
            owner.session,
            owner.stream_id,
            bytes(message.get("data", b"")),
            datagram_id=str(message.get("datagram_id", "datagram")),
            endpoint=owner.endpoint,
        )
        return
    if typ in {"webtransport.close", "webtransport.disconnect"}:
        if owner.closed:
            return
        owner.closed = True
        await owner.handler._send_webtransport_stream_data(
            owner.session,
            owner.stream_id,
            b"",
            end_stream=True,
            endpoint=owner.endpoint,
            priority=True,
        )
        return
    raise RuntimeError(f"unexpected webtransport send message: {typ!r}")


async def _send_stream(owner: Any, message: dict[str, Any]) -> None:
    if not owner.accepted:
        raise RuntimeError("webtransport.stream.send before webtransport.accept")
    direction = str(message.get("stream_direction", "bidi"))
    if direction not in {"bidi", "server_to_client"}:
        raise RuntimeError(
            "webtransport.stream.send requires bidi or server_to_client stream_direction"
        )
    logical_id = str(message.get("stream_id", owner.stream_id))
    if direction == "server_to_client":
        target_id = owner.server_stream_ids.get(logical_id)
        if target_id is None:
            target_id = await owner.handler._open_webtransport_server_stream(
                owner.session,
                owner.stream_id,
                endpoint=owner.endpoint,
            )
            owner.server_stream_ids[logical_id] = target_id
    else:
        target_id = int(logical_id)
    if "more" not in message or not isinstance(message["more"], bool):
        raise RuntimeError(
            "webtransport.stream.send requires explicit boolean more continuation"
        )
    more = message["more"]
    await owner.handler._send_webtransport_stream_data(
        owner.session,
        target_id,
        bytes(message.get("data", b"")),
        end_stream=not more,
        endpoint=owner.endpoint,
        priority=direction == "bidi" or bool(message.get("priority", False)),
    )
    if direction == "server_to_client" and not more:
        owner.server_stream_ids.pop(logical_id, None)


async def _close_stream(owner: Any, message: dict[str, Any]) -> None:
    if not owner.accepted:
        raise RuntimeError("webtransport.stream.close before webtransport.accept")
    logical_id = str(message.get("stream_id", ""))
    if not logical_id:
        raise RuntimeError("webtransport.stream.close requires stream_id")
    direction = str(message.get("stream_direction", "server_to_client"))
    if direction == "server_to_client":
        target_id = owner.server_stream_ids.pop(logical_id, None)
        if target_id is None:
            return
    elif direction == "bidi":
        target_id = int(logical_id)
    else:
        raise RuntimeError(
            "webtransport.stream.close requires bidi or server_to_client stream_direction"
        )
    await owner.handler._send_webtransport_stream_data(
        owner.session,
        target_id,
        b"",
        end_stream=True,
        endpoint=owner.endpoint,
        priority=True,
    )


__all__ = ["send_message"]
