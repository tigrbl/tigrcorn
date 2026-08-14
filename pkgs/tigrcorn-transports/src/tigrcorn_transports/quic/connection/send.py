from __future__ import annotations

from .imports import *

class QuicConnectionSendMixin:
    def _packet_wire_size(
        self,
        *,
        packet_space: str,
        frames: list[object],
        token: bytes | None = None,
    ) -> int:
        destination_connection_id = self.remote_cid or self.local_cid
        plaintext_length = sum(len(encode_frame(frame)) for frame in frames)
        protected_payload_length = plaintext_length + 16
        packet_number = self._space_state(packet_space).send.to_bytes(4, 'big')
        if packet_space == PACKET_SPACE_APPLICATION:
            packet = QuicShortHeaderPacket(
                destination_connection_id=destination_connection_id,
                packet_number=packet_number,
                payload=b'\x00' * protected_payload_length,
                key_phase=bool(self._send_key_phase),
            )
            return len(packet.header_bytes()) + protected_payload_length
        packet_type = {
            PACKET_SPACE_INITIAL: QuicLongHeaderType.INITIAL,
            PACKET_SPACE_HANDSHAKE: QuicLongHeaderType.HANDSHAKE,
            PACKET_SPACE_ZERO_RTT: QuicLongHeaderType.ZERO_RTT,
        }[packet_space]
        packet = QuicLongHeaderPacket(
            packet_type=packet_type,
            version=self.version,
            destination_connection_id=destination_connection_id,
            source_connection_id=self.local_cid,
            packet_number=packet_number,
            payload=b'\x00' * protected_payload_length,
            token=(self._retry_token if token is None else token) if packet_space == PACKET_SPACE_INITIAL else b'',
        )
        wire_size = len(packet.header_bytes()) + protected_payload_length
        if packet_space == PACKET_SPACE_INITIAL and self.is_client:
            wire_size = max(wire_size, _MIN_INITIAL_DATAGRAM_SIZE)
        return wire_size

    def _crypto_chunk_size(self, *, packet_space: str, offset: int, remaining: bytes) -> int:
        budget = self._effective_send_datagram_size()
        low, high = 0, min(len(remaining), budget)
        while low < high:
            candidate = (low + high + 1) // 2
            size = self._packet_wire_size(
                packet_space=packet_space,
                frames=[QuicCryptoFrame(offset=offset, data=remaining[:candidate])],
            )
            if size <= budget:
                low = candidate
            else:
                high = candidate - 1
        if remaining and low == 0:
            raise ProtocolError('effective UDP payload ceiling cannot carry a QUIC CRYPTO frame')
        return low
    def _record_packet_send(
        self,
        *,
        packet_space: str,
        packet_number: int,
        raw: bytes,
        frames: list[object],
        token: bytes | None = None,
        is_pto_probe: bool = False,
    ) -> None:
        recovery_space = self._recovery_space(packet_space)
        path_state = self._path_state(self._active_path_key)
        ack_eliciting = self._ack_eliciting(frames)
        path_state.recovery.on_packet_sent(
            packet_number,
            len(raw),
            ack_eliciting=ack_eliciting,
            packet_space=recovery_space,
            is_pto_probe=is_pto_probe,
            transmitted=not self._deferred_send_accounting,
        )
        self._sent_packets[(recovery_space, packet_number)] = _SentPacketMeta(
            packet_space=packet_space,
            packet_number=packet_number,
            frames=list(frames),
            raw=raw,
            path_key=path_state.key,
            token=token,
            ack_eliciting=ack_eliciting,
            is_pto_probe=is_pto_probe,
            transmitted=not self._deferred_send_accounting,
        )
        self._register_datagram_packets(raw, [(recovery_space, packet_number)])
        if not self._deferred_send_accounting:
            self.bytes_sent += len(raw)
        self._refresh_congestion_snapshot(path_state.recovery)
        self._update_runtime_timers()

    def _encode_long(
        self,
        *,
        packet_type: QuicLongHeaderType,
        packet_space: str,
        frames: list[object],
        token: bytes = b'',
        keys: QuicPacketProtectionKeys,
        is_pto_probe: bool = False,
    ) -> bytes:
        validate_frames_for_packet_space(frames, packet_space, is_client=self.is_client)
        if self.remote_cid is None:
            self.remote_cid = self.local_cid
        if self.is_client and packet_type == QuicLongHeaderType.INITIAL and self._original_destination_connection_id is None:
            self._original_destination_connection_id = self.remote_cid
        state = self._space_state(packet_space)
        packet_number = state.send
        pn_bytes = packet_number.to_bytes(4, 'big')
        plaintext = b''.join(encode_frame(frame) for frame in frames)
        original_plaintext_length = len(plaintext)
        packet = QuicLongHeaderPacket(
            packet_type=packet_type,
            version=self.version,
            destination_connection_id=self.remote_cid,
            source_connection_id=self.local_cid,
            packet_number=pn_bytes,
            payload=b'\x00' * (len(plaintext) + 16),
            token=token,
        )
        if packet_type == QuicLongHeaderType.INITIAL and self.is_client:
            while True:
                packet_length = len(packet.header_bytes()) + len(plaintext) + 16
                if packet_length < _MIN_INITIAL_DATAGRAM_SIZE:
                    plaintext += b'\x00' * (_MIN_INITIAL_DATAGRAM_SIZE - packet_length)
                elif packet_length > _MIN_INITIAL_DATAGRAM_SIZE and len(plaintext) > original_plaintext_length:
                    trim = min(packet_length - _MIN_INITIAL_DATAGRAM_SIZE, len(plaintext) - original_plaintext_length)
                    plaintext = plaintext[:-trim]
                else:
                    break
                packet = QuicLongHeaderPacket(
                    packet_type=packet_type,
                    version=self.version,
                    destination_connection_id=self.remote_cid,
                    source_connection_id=self.local_cid,
                    packet_number=pn_bytes,
                    payload=b'\x00' * (len(plaintext) + 16),
                    token=token,
                )
        raw = protect_quic_packet(
            packet.header_bytes(),
            plaintext,
            packet_number=packet_number,
            pn_offset=packet.pn_offset,
            keys=keys,
        )
        if len(raw) > self._effective_send_datagram_size():
            raise ProtocolError('encoded QUIC packet exceeds effective UDP payload ceiling')
        state.send += 1
        self._sync_packet_number_snapshot()
        self._record_packet_send(
            packet_space=packet_space,
            packet_number=packet_number,
            raw=raw,
            frames=frames,
            token=token or None,
            is_pto_probe=is_pto_probe,
        )
        return raw

    def _encode_initial(self, frames: list[object], *, token: bytes | None = None, is_pto_probe: bool = False) -> bytes:
        self._refresh_tls_key_material()
        client_keys, server_keys = self._initial_keys()
        keys = client_keys if self.is_client else server_keys
        token_bytes = self._retry_token if token is None else token
        return self._encode_long(
            packet_type=QuicLongHeaderType.INITIAL,
            packet_space=PACKET_SPACE_INITIAL,
            frames=frames,
            token=token_bytes,
            keys=keys,
            is_pto_probe=is_pto_probe,
        )

    def _encode_handshake(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        return self._encode_long(
            packet_type=QuicLongHeaderType.HANDSHAKE,
            packet_space=PACKET_SPACE_HANDSHAKE,
            frames=frames,
            keys=self._send_handshake_keys(),
            is_pto_probe=is_pto_probe,
        )

    def _encode_zero_rtt(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        return self._encode_long(
            packet_type=QuicLongHeaderType.ZERO_RTT,
            packet_space=PACKET_SPACE_ZERO_RTT,
            frames=frames,
            keys=self._send_0rtt_keys(),
            is_pto_probe=is_pto_probe,
        )

    def _encode_short(self, frames: list[object], *, is_pto_probe: bool = False) -> bytes:
        validate_frames_for_packet_space(frames, PACKET_SPACE_APPLICATION, is_client=self.is_client)
        if self.remote_cid is None:
            self.remote_cid = self.local_cid
        state = self._space_state(PACKET_SPACE_APPLICATION)
        packet_number = state.send
        pn_bytes = packet_number.to_bytes(4, 'big')
        plaintext = b''.join(encode_frame(frame) for frame in frames)
        packet = QuicShortHeaderPacket(
            destination_connection_id=self.remote_cid,
            packet_number=pn_bytes,
            payload=b'\x00' * (len(plaintext) + 16),
            key_phase=bool(self._send_key_phase),
        )
        raw = protect_quic_packet(
            packet.header_bytes(),
            plaintext,
            packet_number=packet_number,
            pn_offset=packet.pn_offset,
            keys=self._send_1rtt_keys,
        )
        if len(raw) > self._effective_send_datagram_size():
            raise ProtocolError('encoded QUIC packet exceeds effective UDP payload ceiling')
        state.send += 1
        self._sync_packet_number_snapshot()
        self._record_packet_send(
            packet_space=PACKET_SPACE_APPLICATION,
            packet_number=packet_number,
            raw=raw,
            frames=frames,
            is_pto_probe=is_pto_probe,
        )
        return raw

    def send_frames(
        self,
        frames: list[object],
        *,
        packet_space: str = PACKET_SPACE_APPLICATION,
        token: bytes | None = None,
        is_pto_probe: bool = False,
    ) -> bytes:
        if packet_space == PACKET_SPACE_INITIAL:
            return self._encode_initial(frames, token=token, is_pto_probe=is_pto_probe)
        if packet_space == PACKET_SPACE_HANDSHAKE:
            return self._encode_handshake(frames, is_pto_probe=is_pto_probe)
        if packet_space == PACKET_SPACE_ZERO_RTT:
            return self._encode_zero_rtt(frames, is_pto_probe=is_pto_probe)
        return self._encode_short(frames, is_pto_probe=is_pto_probe)

    def build_coalesced_datagrams(
        self,
        packet_specs: Iterable[tuple[str, list[object], bytes | None] | tuple[str, list[object]]],
    ) -> list[bytes]:
        encoded_packets: list[tuple[str, bytes]] = []
        for spec in packet_specs:
            if len(spec) == 3:  # type: ignore[arg-type]
                packet_space, frames, token = spec  # type: ignore[misc]
            else:
                packet_space, frames = spec  # type: ignore[misc]
                token = None
            encoded_packets.append((packet_space, self.send_frames(frames, packet_space=packet_space, token=token)))
        return self._pack_encoded_packets(encoded_packets)

    def build_initial(self, *, token: bytes | None = None) -> bytes:
        self.state = 'establishing'
        return self._encode_initial([FRAME_PING], token=token)

    def _prepare_stream_window(self, stream_id: int) -> None:
        self.flow.ensure_stream(stream_id)

    def _queue_streams_blocked_if_needed(self, stream_id: int) -> None:
        bidirectional = not stream_is_unidirectional(stream_id)
        if stream_is_local_initiated(stream_id, local_is_client=self.is_client):
            limit = self.streams.peer_stream_limit(bidirectional=bidirectional)
            self._pending_handshake_datagrams.append(self.send_streams_blocked(limit, bidirectional=bidirectional))

    def _queue_flow_blocked_frames(self, stream_id: int, amount: int) -> None:
        self.flow.ensure_stream(stream_id)
        if self.flow.connection_bytes_sent + amount > self.flow.connection_window:
            self._pending_handshake_datagrams.append(self.send_data_blocked())
        if self.flow.stream_bytes_sent[stream_id] + amount > self.flow.stream_windows[stream_id]:
            self._pending_handshake_datagrams.append(self.send_stream_data_blocked(stream_id))

    def _maybe_queue_max_stream_credit(self, stream_id: int) -> None:
        frame = self.streams.maybe_release_peer_stream_credit(stream_id)
        if frame is not None:
            self._pending_handshake_datagrams.append(self._encode_short([frame]))

    def _maybe_queue_receive_credit(self, stream_id: int) -> None:
        connection_limit, stream_limit = self.flow.replenish_receive_windows(stream_id)
        frames: list[object] = []
        if connection_limit is not None:
            frames.append(QuicMaxDataFrame(maximum_data=connection_limit))
        if stream_limit is not None:
            frames.append(
                QuicMaxStreamDataFrame(stream_id=stream_id, maximum_data=stream_limit)
            )
        if frames:
            self._pending_handshake_datagrams.append(self._encode_short(frames))

    def send_stream_data(self, stream_id: int, data: bytes, *, fin: bool = False) -> bytes:
        try:
            stream_state = self.streams.ensure_send_stream(stream_id)
        except ProtocolError:
            self._queue_streams_blocked_if_needed(stream_id)
            raise
        self._prepare_stream_window(stream_id)
        if len(data) and not self.flow.can_send(stream_id, len(data)):
            self._queue_flow_blocked_frames(stream_id, len(data))
            raise ProtocolError('insufficient QUIC flow-control credit')
        offset = stream_state.reserve_send(data, fin=fin)
        if len(data):
            self.flow.consume_send(stream_id, len(data))
        frame = QuicStreamFrame(stream_id=stream_id, offset=offset, data=data, fin=fin)
        self.state = 'established'
        packet = self._encode_short([frame])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def send_stream_data_packets(
        self, stream_id: int, data: bytes, *, fin: bool = False
    ) -> list[bytes]:
        """Encode STREAM data into MTU-safe 1-RTT packets."""
        try:
            stream_state = self.streams.ensure_send_stream(stream_id)
        except ProtocolError:
            self._queue_streams_blocked_if_needed(stream_id)
            raise
        self._prepare_stream_window(stream_id)
        if data and not self.flow.can_send(stream_id, len(data)):
            self._queue_flow_blocked_frames(stream_id, len(data))
            raise ProtocolError('insufficient QUIC flow-control credit')

        packets: list[bytes] = []
        cursor = 0
        budget = self._effective_send_datagram_size()
        while cursor < len(data) or not packets:
            remaining = data[cursor:]
            low, high = 0, min(len(remaining), budget)
            while low < high:
                candidate = (low + high + 1) // 2
                candidate_fin = fin and cursor + candidate == len(data)
                size = self._packet_wire_size(
                    packet_space=PACKET_SPACE_APPLICATION,
                    frames=[
                        QuicStreamFrame(
                            stream_id=stream_id,
                            offset=stream_state.send_offset,
                            data=remaining[:candidate],
                            fin=candidate_fin,
                        )
                    ],
                )
                if size <= budget:
                    low = candidate
                else:
                    high = candidate - 1
            if remaining and low == 0:
                raise ProtocolError(
                    'effective UDP payload ceiling cannot carry a QUIC STREAM frame'
                )
            chunk = remaining[:low]
            chunk_fin = fin and cursor + len(chunk) == len(data)
            offset = stream_state.reserve_send(chunk, fin=chunk_fin)
            if chunk:
                self.flow.consume_send(stream_id, len(chunk))
            packets.append(
                self._encode_short(
                    [
                        QuicStreamFrame(
                            stream_id=stream_id,
                            offset=offset,
                            data=chunk,
                            fin=chunk_fin,
                        )
                    ]
                )
            )
            cursor += len(chunk)
            if not remaining:
                break
        self.state = 'established'
        self._maybe_queue_max_stream_credit(stream_id)
        return packets

    def send_datagram_frame(self, data: bytes) -> bytes:
        if self._packet_wire_size(
            packet_space=PACKET_SPACE_APPLICATION,
            frames=[QuicDatagramFrame(data=bytes(data))],
        ) > self._effective_send_datagram_size():
            raise ProtocolError('QUIC DATAGRAM payload exceeds max_datagram_size')
        self.state = 'established'
        return self._encode_short([QuicDatagramFrame(data=bytes(data))])

    def send_early_stream_data(self, stream_id: int, data: bytes, *, fin: bool = False) -> bytes:
        stream_state = self.streams.ensure_send_stream(stream_id)
        self._prepare_stream_window(stream_id)
        if len(data) and not self.flow.can_send(stream_id, len(data)):
            raise ProtocolError('insufficient QUIC flow-control credit')
        offset = stream_state.reserve_send(data, fin=fin)
        if len(data):
            self.flow.consume_send(stream_id, len(data))
        frame = QuicStreamFrame(stream_id=stream_id, offset=offset, data=data, fin=fin)
        self.state = 'establishing'
        packet = self._encode_zero_rtt([frame])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def _encode_crypto_packets(
        self,
        data: bytes,
        *,
        offset: int | None = None,
        packet_space: str = PACKET_SPACE_INITIAL,
    ) -> list[tuple[str, bytes]]:
        state = self._space_state(packet_space)
        frame_offset = state.crypto_send_offset if offset is None else offset
        self.state = 'establishing'
        encoded: list[tuple[str, bytes]] = []
        cursor = 0
        while cursor < len(data) or not encoded:
            remaining = data[cursor:]
            chunk_size = self._crypto_chunk_size(
                packet_space=packet_space,
                offset=frame_offset + cursor,
                remaining=remaining,
            )
            chunk = remaining[:chunk_size]
            raw = self.send_frames(
                [QuicCryptoFrame(offset=frame_offset + cursor, data=chunk)],
                packet_space=packet_space,
            )
            if len(raw) > self._effective_send_datagram_size():
                raise ProtocolError('encoded QUIC CRYPTO packet exceeds effective UDP payload ceiling')
            encoded.append((packet_space, raw))
            if not remaining:
                break
            cursor += chunk_size
        state.crypto_send_offset = max(state.crypto_send_offset, frame_offset + len(data))
        return encoded

    def send_crypto_data(self, data: bytes, *, offset: int | None = None, packet_space: str = PACKET_SPACE_INITIAL) -> bytes:
        datagrams = self._pack_encoded_packets(
            self._encode_crypto_packets(data, offset=offset, packet_space=packet_space)
        )
        first, *rest = datagrams
        self._pending_handshake_datagrams.extend(rest)
        return first

    def _queue_handshake_payload(self, payload: bytes) -> bytes:
        if self.handshake_driver is None:
            return self.send_crypto_data(payload, packet_space=PACKET_SPACE_INITIAL)
        flights = self.handshake_driver.outbound_flights(payload)
        if not flights:
            return b''
        encoded_packets = [
            packet
            for flight in flights
            for packet in self._encode_crypto_packets(flight.data, packet_space=flight.packet_space)
        ]
        datagrams = self._pack_encoded_packets(encoded_packets)
        first, *rest = datagrams
        self._pending_handshake_datagrams.extend(rest)
        return first

    def path_challenge(self, data: bytes) -> bytes:
        self.path_challenges.add(data)
        return self._encode_short([QuicPathChallengeFrame(data=data)])

    def path_response(self, data: bytes) -> bytes:
        return self._encode_short([QuicPathResponseFrame(data=data)])

    def handshake_done(self) -> bytes:
        self.state = 'established'
        self._handshake_done_sent = True
        return self._encode_short([QuicHandshakeDoneFrame()])

    def acknowledge(self, packet_number: int | None = None, *, packet_space: str = PACKET_SPACE_APPLICATION) -> bytes:
        if packet_number is not None:
            self._mark_received(packet_space, packet_number)
        frame = self._build_ack_frame(packet_space)
        if packet_space == PACKET_SPACE_INITIAL:
            return self._encode_initial([frame])
        if packet_space == PACKET_SPACE_HANDSHAKE:
            return self._encode_handshake([frame])
        return self._encode_short([frame])

    def credit_connection(self, amount: int) -> bytes:
        self.flow.expand_local_connection_limit(amount)
        return self._encode_short([QuicMaxDataFrame(maximum_data=self.flow.local_connection_window)])

    def credit_stream(self, stream_id: int, amount: int) -> bytes:
        self.flow.expand_local_stream_limit(stream_id, amount)
        return self._encode_short([QuicMaxStreamDataFrame(stream_id=stream_id, maximum_data=self.flow.receive_window_for_stream(stream_id))])

    def send_data_blocked(self) -> bytes:
        return self._encode_short([QuicDataBlockedFrame(limit=max(self.flow.connection_window, 0))])

    def send_stream_data_blocked(self, stream_id: int) -> bytes:
        self.flow.ensure_stream(stream_id)
        return self._encode_short([QuicStreamDataBlockedFrame(stream_id=stream_id, limit=max(self.flow.window_for_stream(stream_id), 0))])

    def send_streams_blocked(self, limit: int, *, bidirectional: bool = True) -> bytes:
        return self._encode_short([QuicStreamsBlockedFrame(limit=limit, bidirectional=bidirectional)])

    def reset_stream(self, stream_id: int, error_code: int) -> bytes:
        stream_state = self.streams.ensure_send_stream(stream_id)
        stream_state.mark_reset_sent(error_code, final_size=stream_state.send_offset)
        packet = self._encode_short([
            QuicResetStreamFrame(stream_id=stream_id, error_code=error_code, final_size=stream_state.send_final_size or stream_state.send_offset),
        ])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def reset_stream_at(self, stream_id: int, error_code: int, *, reliable_size: int) -> bytes:
        if not (self.peer_transport_parameters and self.peer_transport_parameters.reset_stream_at):
            raise ProtocolError('peer did not negotiate reset_stream_at')
        stream_state = self.streams.ensure_send_stream(stream_id)
        final_size = stream_state.send_offset
        if reliable_size > final_size:
            raise ProtocolError('RESET_STREAM_AT reliable size exceeds final size')
        stream_state.mark_reset_sent(error_code, final_size=final_size)
        packet = self._encode_short([QuicResetStreamAtFrame(stream_id, error_code, final_size, reliable_size)])
        self._maybe_queue_max_stream_credit(stream_id)
        return packet

    def stop_sending(self, stream_id: int, error_code: int) -> bytes:
        stream_state = self.streams.ensure_receive_stream(stream_id)
        stream_state.mark_stop_sending(error_code)
        return self._encode_short([QuicStopSendingFrame(stream_id=stream_id, error_code=error_code)])

    def _build_connection_close_frame(
        self,
        *,
        error_code: int,
        reason: str,
        application: bool,
        packet_space: str,
    ) -> QuicConnectionCloseFrame:
        if application and packet_space in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE}:
            return QuicConnectionCloseFrame(error_code=TRANSPORT_ERROR_APPLICATION_ERROR, reason='', application=False)
        return QuicConnectionCloseFrame(error_code=error_code, reason=reason, application=application)

    def close(
        self,
        error_code: int = 0,
        reason: str = '',
        *,
        application: bool = False,
        packet_space: str = PACKET_SPACE_APPLICATION,
    ) -> bytes:
        self.state = 'closing'
        frame = self._build_connection_close_frame(
            error_code=error_code,
            reason=reason,
            application=application,
            packet_space=packet_space,
        )
        return self.send_frames([frame], packet_space=packet_space)

    def configure_handshake(self, driver: QuicTlsHandshakeDriver) -> None:
        self.handshake_driver = driver
        self._update_local_transport_parameters()

    def start_handshake(self) -> bytes:
        self._refresh_tls_key_material()
        if self.handshake_driver is None:
            return self.build_initial()
        payload = self.handshake_driver.initiate()
        self._refresh_tls_key_material()
        return self._queue_handshake_payload(payload)

    def take_handshake_datagrams(self) -> list[bytes]:
        while self._pending_auto_resets:
            stream_id, error_code = self._pending_auto_resets.pop(0)
            self._pending_handshake_datagrams.append(self.reset_stream(stream_id, error_code))
        items = list(self._pending_handshake_datagrams)
        self._pending_handshake_datagrams.clear()
        return items
