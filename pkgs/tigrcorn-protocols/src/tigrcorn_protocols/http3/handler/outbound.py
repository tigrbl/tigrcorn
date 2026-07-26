from __future__ import annotations

from .imports import *

class HTTP3OutboundMixin:
    def _queue_or_send(self, session: HTTP3Session, raw: bytes, endpoint: UDPEndpoint, addr: tuple[str, int]) -> None:
        transport = getattr(endpoint, 'transport', None)
        if transport is not None and transport.is_closing():
            return
        if self._can_send_now(session, raw):
            session.quic.confirm_datagram_sent(raw)
            endpoint.send(raw, addr)
            session.bytes_sent += len(raw)
            if self.metrics is not None:
                self.metrics.quic_datagram_sent(len(raw))
            return
        session.quic.defer_datagram(raw)
        session.pending_outbound.append(raw)

    def _sync_quic_loss_metrics(self, session: HTTP3Session) -> None:
        if self.metrics is None:
            return
        lost_total = int(getattr(session.quic, 'packets_lost_total', 0))
        if lost_total > session.last_quic_packets_lost_total:
            self.metrics.quic_packets_lost_observed(lost_total - session.last_quic_packets_lost_total)
        session.last_quic_packets_lost_total = lost_total
        pto_total = int(getattr(session.quic, 'pto_expirations_total', 0))
        while pto_total > session.last_quic_pto_expirations_total:
            self.metrics.quic_pto_expired()
            session.last_quic_pto_expirations_total += 1

    def _flush_pending_outbound(self, session: HTTP3Session, endpoint: UDPEndpoint) -> None:
        if not session.pending_priority_outbound and not session.pending_outbound:
            return
        transport = getattr(endpoint, 'transport', None)
        if transport is not None and transport.is_closing():
            return
        while session.pending_priority_outbound or session.pending_outbound:
            preferred = (
                session.pending_priority_outbound
                if session.outbound_priority_turn
                else session.pending_outbound
            )
            alternate = (
                session.pending_outbound
                if session.outbound_priority_turn
                else session.pending_priority_outbound
            )
            queue = preferred or alternate
            raw = queue[0]
            if not self._can_send_now(session, raw):
                if not alternate or alternate is queue:
                    break
                queue = alternate
                raw = queue[0]
                if not self._can_send_now(session, raw):
                    break
            queue.pop(0)
            session.quic.confirm_datagram_sent(raw)
            endpoint.send(raw, session.addr)
            session.bytes_sent += len(raw)
            if self.metrics is not None:
                self.metrics.quic_datagram_sent(len(raw))
            session.outbound_priority_turn = queue is session.pending_outbound

    def _can_send_now(self, session: HTTP3Session, raw: bytes) -> bool:
        amplification_ok = session.address_validated or (session.bytes_sent + len(raw) <= (session.bytes_received * 3))
        return amplification_ok and session.quic.can_transmit_datagram(raw)

    def _cancel_session_timer(self, session: HTTP3Session) -> None:
        if session.timer_handle is not None:
            session.timer_handle.cancel()
            session.timer_handle = None

    def _next_session_delay(self, session: HTTP3Session) -> float | None:
        delays: list[float] = []
        idle_timeout = float(self.config.quic.idle_timeout)
        if idle_timeout > 0:
            delays.append(
                max(0.0, idle_timeout - (time.monotonic() - session.last_activity_at))
            )
        runtime_delay = session.quic.next_runtime_deadline()
        if runtime_delay is not None:
            delays.append(runtime_delay)
        for raw in (*session.pending_priority_outbound, *session.pending_outbound):
            delay = session.quic.next_transmit_delay(raw)
            if delay is not None:
                delays.append(delay)
        if not delays:
            return None
        return max(0.0, min(delays))

    def _arm_session_timer(self, session: HTTP3Session, endpoint: UDPEndpoint) -> None:
        self._cancel_session_timer(session)
        delay = self._next_session_delay(session)
        if delay is None:
            return
        loop = asyncio.get_running_loop()
        session.timer_handle = loop.call_later(delay, self._fire_session_timer, session, endpoint)

    def _close_session(self, session: HTTP3Session) -> None:
        removed = self.sessions.pop(session.addr, None)
        if removed is session:
            self._close_h3_connection(session, reason='quic-session-close')
            self.trace_webtransport('quic.session.close', **self._trace_session_fields(session))
            self.sessions_by_local_cid.pop(session.quic.local_cid, None)
            if self.metrics is not None:
                self.metrics.quic_session_closed()

    async def close(self) -> None:
        async with self._lock:
            for session in list(self.sessions.values()):
                self._cancel_session_timer(session)
                await self._abort_session_tunnels(session)
                await self._abort_session_websockets(session)
                await self._abort_session_webtransports(session)
                self._close_session(session)
            self.sessions.clear()
            self.sessions_by_local_cid.clear()

    def _fire_session_timer(self, session: HTTP3Session, endpoint: UDPEndpoint) -> None:
        transport = getattr(endpoint, 'transport', None)
        if transport is None or transport.is_closing():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if loop.is_closed():
            return
        loop.create_task(self._on_session_timer(session, endpoint))

    async def _on_session_timer(self, session: HTTP3Session, endpoint: UDPEndpoint) -> None:
        async with self._lock:
            session.timer_handle = None
            transport = getattr(endpoint, 'transport', None)
            if transport is None or transport.is_closing():
                return
            if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
                return
            idle_timeout = float(self.config.quic.idle_timeout)
            if (
                idle_timeout > 0
                and time.monotonic() - session.last_activity_at >= idle_timeout
            ):
                self.trace_webtransport(
                    "quic.connection.idle_timeout",
                    **self._trace_session_fields(session),
                    idle_timeout=idle_timeout,
                )
                await self._abort_session_tunnels(session)
                await self._abort_session_websockets(session)
                await self._abort_session_webtransports(session)
                self._close_session(session)
                return
            outbound = session.quic.drain_scheduled_datagrams()
            for raw in outbound:
                self._queue_or_send(session, raw, endpoint, session.addr)
            self._flush_pending_outbound(session, endpoint)
            self._arm_session_timer(session, endpoint)
    def _ensure_server_control_stream_locked(self, session: HTTP3Session) -> list[bytes]:
        if (
            session.server_control_stream_sent
            or 'http3' not in self.listener.enabled_protocols
            or (not session.address_validated and session.quic.handshake_driver is not None)
        ):
            return []
        if session.server_control_stream_id is None:
            session.server_control_stream_id = session.quic.streams.next_stream_id(client=False, unidirectional=True)
        control_settings = {
            SETTING_QPACK_MAX_TABLE_CAPACITY: 0,
            SETTING_MAX_FIELD_SECTION_SIZE: self.listener.max_datagram_size,
        }
        if self.listener.websocket:
            control_settings[SETTING_ENABLE_CONNECT_PROTOCOL] = 1
        if 'webtransport' in self.listener.enabled_protocols:
            control_settings.update(
                settings_for_profiles(
                    self.config.webtransport.profiles,
                    max_sessions=int(self.config.webtransport.max_sessions or 1),
                )
            )
        control_payload = session.h3.encode_control_stream(control_settings)
        session.server_control_stream_sent = True
        return [session.quic.send_stream_data(session.server_control_stream_id, control_payload, fin=False)]

    def _flush_qpack_streams(self, session: HTTP3Session) -> list[bytes]:
        outbound: list[bytes] = []
        encoder_data = session.h3.take_encoder_stream_data()
        if encoder_data:
            if session.server_qpack_encoder_stream_id is None:
                session.server_qpack_encoder_stream_id = session.quic.streams.next_stream_id(client=False, unidirectional=True)
                encoder_data = encode_quic_varint(STREAM_TYPE_QPACK_ENCODER) + encoder_data
                if self.metrics is not None:
                    self.metrics.http3_qpack_encoder_stream_opened()
            outbound.append(session.quic.send_stream_data(session.server_qpack_encoder_stream_id, encoder_data, fin=False))
        decoder_data = session.h3.take_decoder_stream_data()
        if decoder_data:
            if session.server_qpack_decoder_stream_id is None:
                session.server_qpack_decoder_stream_id = session.quic.streams.next_stream_id(client=False, unidirectional=True)
                decoder_data = encode_quic_varint(STREAM_TYPE_QPACK_DECODER) + decoder_data
                if self.metrics is not None:
                    self.metrics.http3_qpack_decoder_stream_opened()
            outbound.append(session.quic.send_stream_data(session.server_qpack_decoder_stream_id, decoder_data, fin=False))
        return outbound

    def _queue_session_outbound_locked(
        self,
        session: HTTP3Session,
        outbound: list[bytes],
        endpoint: UDPEndpoint,
        *,
        priority: bool = False,
    ) -> None:
        # QuicConnection records packets when they are encoded. Refund the
        # complete batch before admitting it to the wire so later packets do
        # not consume congestion credit ahead of earlier CRYPTO segments.
        for raw in outbound:
            session.quic.defer_datagram(raw)
        target = (
            session.pending_priority_outbound if priority else session.pending_outbound
        )
        target.extend(outbound)
        self._flush_pending_outbound(session, endpoint)
        if session.addr in self.sessions and self.sessions.get(session.addr) is session:
            self._arm_session_timer(session, endpoint)
