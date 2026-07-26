from __future__ import annotations

from .imports import *

class QuicConnectionReceiveMixin:
    def _server_maybe_handle_token_or_retry(
        self,
        packet: QuicLongHeaderPacket,
        *,
        addr: tuple[str, int] | None,
    ) -> list[QuicEvent] | None:
        if self.is_client or packet.packet_type != QuicLongHeaderType.INITIAL:
            return None
        if self._original_destination_connection_id is None:
            self._original_destination_connection_id = packet.destination_connection_id
        if self._peer_initial_source_connection_id is None:
            self._peer_initial_source_connection_id = packet.source_connection_id
        self._update_local_transport_parameters()
        if packet.token:
            token_info = self._validate_address_token(packet.token, addr=addr)
            if token_info is None:
                close_packet = self.close(
                    error_code=TRANSPORT_ERROR_INVALID_TOKEN,
                    reason='invalid token',
                    packet_space=PACKET_SPACE_INITIAL,
                )
                self._pending_handshake_datagrams.append(close_packet)
                return [
                    QuicEvent(
                        kind='close',
                        packet_space=PACKET_SPACE_INITIAL,
                        detail=QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_INVALID_TOKEN, reason='invalid token'),
                    )
                ]
            if token_info.purpose == _TOKEN_PURPOSE_RETRY:
                if token_info.original_destination_connection_id != self._original_destination_connection_id:
                    raise ProtocolError('Retry token original destination connection id mismatch')
                if self._retry_source_connection_id is not None and token_info.retry_source_connection_id not in {b'', self._retry_source_connection_id}:
                    raise ProtocolError('Retry token source connection id mismatch')
                self.address_validated = True
            elif token_info.purpose == _TOKEN_PURPOSE_NEW_TOKEN:
                self.address_validated = True
            else:
                raise ProtocolError('unknown QUIC token purpose')
            return None
        if self.require_retry and not self.address_validated:
            retry = self.build_retry(packet, client_addr=addr)
            self._pending_handshake_datagrams.append(retry)
            return [QuicEvent(kind='retry', detail=decode_packet(retry))]
        return None

    def _handle_retry_packet(self, packet: QuicRetryPacket) -> list[QuicEvent]:
        if not self.is_client:
            raise ProtocolError('servers must not process Retry packets for an active connection')
        if self._received_retry:
            return [QuicEvent(kind='retry_ignored', detail=packet)]
        if not packet.token:
            raise ProtocolError('received Retry packet without a token')
        original_destination_connection_id = self._original_destination_connection_id or self.remote_cid
        if not packet.validate(original_destination_connection_id=original_destination_connection_id):
            raise ProtocolError('invalid Retry integrity tag')
        self._received_retry = True
        self._retry_token = packet.token
        self._retry_source_connection_id = packet.source_connection_id
        self.remote_cid = packet.source_connection_id
        self.recovery.discard_space(PACKET_SPACE_INITIAL)
        self._update_local_transport_parameters()
        return [QuicEvent(kind='retry', detail=packet)]

    def _receive_single_packet(self, data: bytes, *, addr: tuple[str, int] | None) -> list[QuicEvent]:
        try:
            peek = self._peek_packet(data)
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]

        if isinstance(peek, QuicVersionNegotiationPacket):
            self.handle_version_negotiation(peek)
            return [QuicEvent(kind='version_negotiation', detail=peek)]

        if isinstance(peek, QuicLongHeaderPacket) and peek.version not in self.supported_versions:
            if not self.is_client and peek.packet_type in {QuicLongHeaderType.INITIAL, QuicLongHeaderType.ZERO_RTT}:
                version_negotiation = self.build_version_negotiation(
                    destination_connection_id=peek.source_connection_id,
                    source_connection_id=peek.destination_connection_id,
                )
                self._pending_handshake_datagrams.append(version_negotiation)
                detail = decode_packet(version_negotiation)
                return [QuicEvent(kind='version_negotiation_sent', detail=detail)]
            return [QuicEvent(kind='version_negotiation', detail=peek.version)]

        if isinstance(peek, QuicRetryPacket):
            return self._handle_retry_packet(peek)

        if isinstance(peek, QuicLongHeaderPacket):
            maybe_retry = self._server_maybe_handle_token_or_retry(peek, addr=addr)
            if maybe_retry is not None:
                return maybe_retry

        try:
            packet, packet_space, packet_number, plaintext = self._decode_payload(data)
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]

        if isinstance(packet, QuicVersionNegotiationPacket):
            self.handle_version_negotiation(packet)
            return [QuicEvent(kind='version_negotiation', detail=packet)]
        if isinstance(packet, QuicRetryPacket):
            return self._handle_retry_packet(packet)
        if isinstance(packet, QuicStatelessResetPacket):
            self.state = 'closed'
            return [QuicEvent(kind='stateless_reset', detail=packet)]

        if isinstance(packet, QuicLongHeaderPacket):
            if self.is_client and packet.source_connection_id and self._first_server_source_connection_id is None:
                self._first_server_source_connection_id = packet.source_connection_id
            elif not self.is_client and packet.source_connection_id and self._peer_initial_source_connection_id is None:
                self._peer_initial_source_connection_id = packet.source_connection_id
            self.remote_cid = packet.source_connection_id or self.remote_cid
            if not self.is_client:
                self.local_cid = packet.destination_connection_id or self.local_cid
                if self.handshake_driver is not None:
                    self._update_local_transport_parameters()
        self._mark_received(packet_space, packet_number)
        events: list[QuicEvent] = [QuicEvent(kind='packet', packet_number=packet_number, packet_space=packet_space, detail=packet)]
        ack_eliciting_received = False
        offset = 0
        while offset < len(plaintext):
            frame, offset = decode_frame(plaintext, offset)
            validate_frame_for_packet_space(frame, packet_space, is_client=not self.is_client)
            if frame == FRAME_PING:
                ack_eliciting_received = True
                self.state = 'established'
                events.append(QuicEvent(kind='ping', packet_number=packet_number, packet_space=packet_space))
                continue
            if frame == FRAME_PADDING:
                continue
            if isinstance(frame, QuicAckFrame):
                self._handle_ack_frame(frame, packet_space=packet_space)
                events.append(QuicEvent(kind='ack', packet_number=frame.largest_acked, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicCryptoFrame):
                ack_eliciting_received = True
                crypto_data = self._space_state(packet_space).crypto_receive.apply(frame.offset, frame.data)
                should_process_crypto = bool(
                    crypto_data
                    and self.handshake_driver is not None
                    and (not self.handshake_driver.complete or self.is_client)
                )
                if should_process_crypto:
                    was_complete = bool(self.handshake_driver.complete)
                    try:
                        outbound = self.handshake_driver.receive(crypto_data)
                    except ProtocolError as exc:
                        self.state = 'closing'
                        error_code = int(getattr(exc, 'quic_error_code', TRANSPORT_ERROR_PROTOCOL_VIOLATION))
                        self._pending_handshake_datagrams.insert(
                            0,
                            self.close(error_code=error_code, reason=str(exc), packet_space=packet_space),
                        )
                        events.append(QuicEvent(kind='close', packet_space=packet_space, detail=QuicConnectionCloseFrame(error_code=error_code, reason=str(exc))))
                        break
                    self._refresh_tls_key_material()
                    self._apply_peer_transport_parameters()
                    if outbound:
                        first = self._queue_handshake_payload(outbound)
                        if first:
                            self._pending_handshake_datagrams.insert(0, first)
                    if self.handshake_driver.complete:
                        self.address_validated = True
                        self.recovery.discard_space(PACKET_SPACE_INITIAL)
                        if not self.is_client and not self._handshake_done_sent:
                            self._pending_handshake_datagrams.append(self.handshake_done())
                        if not was_complete:
                            events.append(QuicEvent(kind='handshake_complete', packet_number=packet_number, packet_space=packet_space))
                        if self.is_client and self._peer_preferred_address is not None:
                            events.append(QuicEvent(kind='preferred_address', detail=self._peer_preferred_address, packet_space=PACKET_SPACE_APPLICATION))
                events.append(QuicEvent(kind='crypto', data=frame.data, packet_number=packet_number, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicNewTokenFrame):
                ack_eliciting_received = True
                self._peer_new_tokens.append(frame.token)
                events.append(QuicEvent(kind='new_token', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxDataFrame):
                ack_eliciting_received = True
                self.flow.update_send_limit_connection(frame.maximum_data)
                events.append(QuicEvent(kind='max_data', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxStreamDataFrame):
                ack_eliciting_received = True
                self.flow.update_send_limit_stream(frame.stream_id, frame.maximum_data)
                events.append(QuicEvent(kind='max_stream_data', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicMaxStreamsFrame):
                ack_eliciting_received = True
                self.streams.update_peer_max_streams(frame.maximum_streams, bidirectional=frame.bidirectional)
                events.append(QuicEvent(kind='max_streams', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicDataBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='data_blocked', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStreamDataBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='stream_data_blocked', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStreamsBlockedFrame):
                ack_eliciting_received = True
                events.append(QuicEvent(kind='streams_blocked', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicNewConnectionIdFrame):
                ack_eliciting_received = True
                if frame.retire_prior_to > frame.sequence:
                    raise ProtocolError('invalid retire_prior_to in NEW_CONNECTION_ID')
                if len(self.peer_connection_ids) >= self._peer_active_connection_id_limit and frame.sequence not in self.peer_connection_ids:
                    raise ProtocolError('peer exceeded active_connection_id_limit')
                self.peer_connection_ids[frame.sequence] = (frame.connection_id, frame.stateless_reset_token)
                for sequence in [sequence for sequence in self.peer_connection_ids if sequence < frame.retire_prior_to]:
                    self.peer_connection_ids.pop(sequence, None)
                    self.retire_connection_ids.append(sequence)
                events.append(QuicEvent(kind='new_connection_id', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicRetireConnectionIdFrame):
                ack_eliciting_received = True
                self.issued_connection_ids.pop(frame.sequence, None)
                events.append(QuicEvent(kind='retire_connection_id', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicPathChallengeFrame):
                ack_eliciting_received = True
                self._pending_handshake_datagrams.append(self.path_response(frame.data))
                events.append(QuicEvent(kind='path_challenge', data=frame.data, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicPathResponseFrame):
                ack_eliciting_received = True
                if frame.data in self.path_challenges:
                    self.address_validated = True
                    self.path_challenges.discard(frame.data)
                events.append(QuicEvent(kind='path_response', data=frame.data, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicHandshakeDoneFrame):
                ack_eliciting_received = True
                self.state = 'established'
                self.address_validated = True
                self.recovery.discard_space(PACKET_SPACE_HANDSHAKE)
                events.append(QuicEvent(kind='handshake_done', packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicDatagramFrame):
                ack_eliciting_received = True
                self.state = 'established'
                events.append(QuicEvent(kind='datagram', data=frame.data, packet_number=packet_number, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicResetStreamFrame):
                ack_eliciting_received = True
                self.flow.validate_receive(frame.stream_id, final_size=frame.final_size)
                self.streams.apply_reset(frame)
                self.flow.commit_receive(frame.stream_id, final_size=frame.final_size)
                self._maybe_queue_max_stream_credit(frame.stream_id)
                events.append(QuicEvent(kind='reset_stream', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicResetStreamAtFrame):
                if not (self.local_transport_parameters and self.local_transport_parameters.reset_stream_at):
                    raise ProtocolError('RESET_STREAM_AT received without transport parameter negotiation')
                ack_eliciting_received = True
                self.flow.validate_receive(frame.stream_id, final_size=frame.final_size)
                self.streams.apply_reset_at(frame)
                self.flow.commit_receive(frame.stream_id, final_size=frame.final_size)
                self._maybe_queue_max_stream_credit(frame.stream_id)
                events.append(QuicEvent(kind='reset_stream_at', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicStopSendingFrame):
                ack_eliciting_received = True
                stream_state = self.streams.ensure_send_stream(frame.stream_id)
                stream_state.mark_stop_sending(frame.error_code)
                if not stream_state.send_terminal:
                    self._pending_auto_resets.append((frame.stream_id, frame.error_code))
                events.append(QuicEvent(kind='stop_sending', stream_id=frame.stream_id, packet_space=packet_space, detail=frame))
                continue
            if isinstance(frame, QuicConnectionCloseFrame):
                self.state = 'draining'
                events.append(QuicEvent(kind='application_close' if frame.application else 'transport_close', packet_space=packet_space, detail=frame))
                events.append(QuicEvent(kind='close', packet_space=packet_space, detail=frame))
                break
            if isinstance(frame, QuicStreamFrame):
                ack_eliciting_received = True
                final_size = frame.offset + len(frame.data) if frame.fin else None
                self.flow.validate_receive(frame.stream_id, end_offset=frame.offset + len(frame.data), final_size=final_size)
                stream_state = self.streams.ensure_receive_stream(frame.stream_id)
                data_chunk, _delta = stream_state.apply_with_metrics(frame)
                self.flow.commit_receive(frame.stream_id, end_offset=frame.offset + len(frame.data), final_size=final_size)
                if _delta > 0:
                    self._maybe_queue_receive_credit(frame.stream_id)
                self._maybe_queue_max_stream_credit(frame.stream_id)
                self.state = 'established'
                events.append(
                    QuicEvent(
                        kind='stream',
                        stream_id=frame.stream_id,
                        data=data_chunk,
                        fin=stream_state.received_final,
                        packet_number=packet_number,
                        packet_space=packet_space,
                        detail=frame,
                    )
                )
                continue
        if ack_eliciting_received:
            self._schedule_ack(packet_space, immediate=packet_space in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE})
        self._run_loss_detection()
        return events

    def receive_datagram(self, data: bytes, *, addr: tuple[str, int] | None = None) -> list[QuicEvent]:
        self.bytes_received += len(data)
        try:
            path_event = self._observe_path(addr)
        except ProtocolError as exc:
            self.state = 'closing'
            self._pending_handshake_datagrams.append(
                self.close(error_code=TRANSPORT_ERROR_PROTOCOL_VIOLATION, reason=str(exc))
            )
            return [QuicEvent(kind='close', detail=QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_PROTOCOL_VIOLATION, reason=str(exc)))]
        try:
            packets = split_coalesced_packets(data, destination_connection_id_length=max(len(self.local_cid), 1))
        except ProtocolError:
            stateless_reset = self._maybe_stateless_reset(data)
            if stateless_reset is not None:
                self.state = 'closed'
                return [QuicEvent(kind='stateless_reset', detail=stateless_reset)]
            return [QuicEvent(kind='integrity_error')]
        events: list[QuicEvent] = []
        if path_event is not None:
            events.append(path_event)
        for packet in packets:
            events.extend(self._receive_single_packet(packet, addr=addr))
        return events
