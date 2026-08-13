from __future__ import annotations

import asyncio
from typing import Any

from .imports import *

_STREAM_CHUNK_BYTES = 16 * 1024
_OUTBOUND_MAX_PENDING_DATAGRAMS = 32
_OUTBOUND_DRAIN_POLL_SECONDS = 0.001


class HTTP3WebTransportStreamFlowMixin:
    async def _open_webtransport_server_stream(
        self,
        session: HTTP3Session,
        owner_stream_id: int,
        *,
        endpoint: UDPEndpoint,
    ) -> int:
        async with session.lock:
            if (
                session.addr not in self.sessions
                or self.sessions.get(session.addr) is not session
            ):
                raise ProtocolError("WebTransport session is no longer connected")
            webtransport = session.webtransport_sessions.get(owner_stream_id)
            if webtransport is None or webtransport.closed:
                raise ProtocolError("WebTransport session is no longer active")
            stream_id = session.quic.streams.next_stream_id(
                client=False,
                unidirectional=True,
            )
            session.webtransport_streams.add(stream_id)
            session.webtransport_stream_owners[stream_id] = owner_stream_id
            self._webtransport_register_stream(webtransport, stream_id)
            return stream_id


async def _wait_for_outbound_capacity(
    handler: Any,
    session: Any,
    endpoint: Any,
    *,
    max_pending: int,
) -> bool:
    while True:
        async with session.lock:
            if (
                session.addr not in handler.sessions
                or handler.sessions.get(session.addr) is not session
            ):
                return False
            handler._flush_pending_outbound(session, endpoint)
            if len(session.pending_outbound) < max_pending:
                return True
        await asyncio.sleep(_OUTBOUND_DRAIN_POLL_SECONDS)


async def send_nonpriority_stream_data(
    handler: Any,
    session: Any,
    stream_id: int,
    data: bytes,
    *,
    end_stream: bool,
    endpoint: Any,
) -> None:
    """Bound queued media packets while leaving gaps for control responses."""
    chunks = [
        data[offset : offset + _STREAM_CHUNK_BYTES]
        for offset in range(0, len(data), _STREAM_CHUNK_BYTES)
    ] or [b""]
    for index, chunk in enumerate(chunks):
        if not await _wait_for_outbound_capacity(
            handler,
            session,
            endpoint,
            max_pending=_OUTBOUND_MAX_PENDING_DATAGRAMS,
        ):
            return
        async with session.lock:
            await handler._send_webtransport_stream_data(
                session,
                stream_id,
                chunk,
                end_stream=end_stream and index == len(chunks) - 1,
                endpoint=endpoint,
                already_locked=True,
                priority=False,
            )
        await asyncio.sleep(0)
    await _wait_for_outbound_capacity(
        handler,
        session,
        endpoint,
        max_pending=1,
    )


__all__ = [
    "HTTP3WebTransportStreamFlowMixin",
    "send_nonpriority_stream_data",
]
