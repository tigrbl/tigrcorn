from __future__ import annotations

from .imports import *

class HTTP3WebTransportDatagramsMixin:
    def _encode_webtransport_datagram_payload(self, stream_id: int, data: bytes) -> bytes:
        if len(data) > self._webtransport_max_datagram_size():
            raise ProtocolError('webtransport.max_datagram_size exceeded')
        quarter_stream_id = stream_id // 4
        return encode_quic_varint(quarter_stream_id) + data

    def _decode_webtransport_datagram_payload(self, payload: bytes) -> tuple[int, bytes]:
        quarter_stream_id, offset = decode_quic_varint(payload, 0)
        return int(quarter_stream_id) * 4, payload[offset:]
    async def _dispatch_webtransport_datagram_locked(self, session: HTTP3Session, payload: bytes) -> None:
        try:
            stream_id, data = self._decode_webtransport_datagram_payload(payload)
        except ProtocolError:
            return
        webtransport = session.webtransport_sessions.get(stream_id)
        if webtransport is None:
            self.trace_webtransport(
                'webtransport.datagram.orphan',
                **self._trace_session_fields(session),
                stream_id=stream_id,
                bytes=len(data),
            )
            return
        if len(data) > self._webtransport_max_datagram_size():
            return
        datagram_id = f'{stream_id}:{getattr(session, "request_packets", 0)}'
        budget_result = self._webtransport_register_datagram(webtransport, datagram_id, data)
        if budget_result is not None and not budget_result.get("accepted", False):
            self.trace_webtransport(
                'webtransport.datagram.budget.reject',
                **self._trace_session_fields(session),
                session_id=webtransport.session_id,
                stream_id=stream_id,
                datagram_id=datagram_id,
                reason=budget_result.get("reason"),
                closed=bool(budget_result.get("closed")),
            )
            if budget_result.get("closed"):
                await webtransport.abort()
            return
        self.trace_webtransport(
            'webtransport.datagram.dispatch',
            **self._trace_session_fields(session),
            session_id=webtransport.session_id,
            stream_id=stream_id,
            datagram_id=datagram_id,
            bytes=len(data),
        )
        await webtransport.feed_datagram(datagram_id, data)
    async def _send_webtransport_datagram(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        datagram_id: str,
        endpoint: UDPEndpoint,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with session.lock:
                await self._send_webtransport_datagram(
                    session,
                    stream_id,
                    data,
                    datagram_id=datagram_id,
                    endpoint=endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        if stream_id not in session.webtransport_sessions:
            self.trace_webtransport(
                'webtransport.datagram.send.drop',
                **self._trace_session_fields(session),
                stream_id=stream_id,
                datagram_id=datagram_id,
                reason='missing-session',
            )
            return
        budget_result = self._webtransport_register_datagram(session.webtransport_sessions[stream_id], datagram_id, data)
        if budget_result is not None and not budget_result.get("accepted", False):
            self.trace_webtransport(
                'webtransport.datagram.send.budget.reject',
                **self._trace_session_fields(session),
                session_id=session.webtransport_sessions[stream_id].session_id,
                stream_id=stream_id,
                datagram_id=datagram_id,
                reason=budget_result.get("reason"),
                closed=bool(budget_result.get("closed")),
            )
            if budget_result.get("closed"):
                await session.webtransport_sessions[stream_id].abort()
            return
        payload = self._encode_webtransport_datagram_payload(stream_id, data)
        self.trace_webtransport(
            'webtransport.datagram.send',
            **self._trace_session_fields(session),
            session_id=session.webtransport_sessions[stream_id].session_id,
            stream_id=stream_id,
            datagram_id=datagram_id,
            bytes=len(data),
        )
        outbound = [session.quic.send_datagram_frame(payload)]
        self._queue_session_outbound_locked(session, outbound, endpoint)
