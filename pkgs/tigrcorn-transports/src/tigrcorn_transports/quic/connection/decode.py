from __future__ import annotations

from .imports import *

class QuicConnectionDecodeMixin:
    def suppress_pending_reset(self, stream_id: int) -> None:
        self._pending_auto_resets = [
            (pending_stream_id, error_code)
            for pending_stream_id, error_code in self._pending_auto_resets
            if pending_stream_id != stream_id
        ]

    def take_pending_datagrams(self) -> list[bytes]:
        return self.take_handshake_datagrams() + self.drain_scheduled_datagrams()

    def can_send_amplification_limited(self, size: int) -> bool:
        if self.address_validated or self.is_client:
            return True
        return self.bytes_sent + size <= (self.bytes_received * 3)

    def can_send_packet(self, size: int) -> bool:
        if not self.can_send_amplification_limited(size):
            return False
        return self.recovery.can_send(size)

    def issue_connection_id(self, *, sequence: int | None = None) -> tuple[int, bytes, bytes, bytes]:
        if sequence is None:
            sequence = self.connection_id_sequence
            self.connection_id_sequence += 1
        if len(self.issued_connection_ids) >= self._peer_active_connection_id_limit:
            raise ProtocolError('peer active_connection_id_limit would be exceeded')
        cid = generate_connection_id()
        token = derive_secret(cid + self.secret, b'stateless-reset', length=16)
        self.issued_connection_ids[sequence] = (cid, token)
        return sequence, cid, token, self._encode_short([
            QuicNewConnectionIdFrame(sequence=sequence, retire_prior_to=0, connection_id=cid, stateless_reset_token=token),
        ])

    def retire_connection_id(self, sequence: int) -> bytes:
        self.retire_connection_ids.append(sequence)
        self.issued_connection_ids.pop(sequence, None)
        return self._encode_short([QuicRetireConnectionIdFrame(sequence=sequence)])

    def issue_new_token(self, *, addr: tuple[str, int] | None) -> tuple[bytes, bytes]:
        if self.is_client:
            raise ProtocolError('only servers can issue NEW_TOKEN frames')
        token = self._issue_address_token(purpose=_TOKEN_PURPOSE_NEW_TOKEN, addr=addr)
        return token, self._encode_short([QuicNewTokenFrame(token=token)])

    def build_retry(
        self,
        initial: QuicLongHeaderPacket,
        *,
        client_addr: tuple[str, int] | None,
        source_connection_id: bytes | None = None,
    ) -> bytes:
        if self.is_client:
            raise ProtocolError('clients cannot send Retry packets')
        if initial.packet_type != QuicLongHeaderType.INITIAL:
            raise ProtocolError('Retry can only be sent in response to an Initial packet')
        retry_scid = source_connection_id or generate_connection_id()
        token = self._issue_address_token(
            purpose=_TOKEN_PURPOSE_RETRY,
            addr=client_addr,
            original_destination_connection_id=initial.destination_connection_id,
            retry_source_connection_id=retry_scid,
        )
        retry = QuicRetryPacket(
            version=initial.version,
            destination_connection_id=initial.source_connection_id,
            source_connection_id=retry_scid,
            token=token,
        )
        self._sent_retry = True
        self._retry_source_connection_id = retry_scid
        self._original_destination_connection_id = initial.destination_connection_id
        self._update_local_transport_parameters()
        return retry.encode(original_destination_connection_id=initial.destination_connection_id)

    def build_version_negotiation(
        self,
        *,
        destination_connection_id: bytes,
        source_connection_id: bytes | None = None,
        supported_versions: Sequence[int] | None = None,
    ) -> bytes:
        packet = QuicVersionNegotiationPacket(
            destination_connection_id=destination_connection_id,
            source_connection_id=source_connection_id if source_connection_id is not None else self.local_cid,
            supported_versions=list(supported_versions or self.supported_versions),
        )
        return packet.encode()

    def handle_version_negotiation(self, packet: QuicVersionNegotiationPacket) -> bool:
        if not self.is_client:
            return False
        if self.version in packet.supported_versions:
            return False
        for candidate in self.supported_versions:
            if candidate in packet.supported_versions:
                self.version = candidate
                self.state = 'version_negotiated'
                return True
        self.state = 'version_negotiation_failed'
        return False

    def build_stateless_reset(self, token: bytes) -> bytes:
        return QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=secrets.token_bytes(5)).encode()

    def _mark_received(self, packet_space: str, packet_number: int) -> None:
        state = self._space_state(packet_space)
        state.received_packets.add(packet_number)
        state.received_packet_times[packet_number] = time.monotonic()
        state.largest_received = max(state.largest_received, packet_number)
        self._sync_packet_number_snapshot()

    def _build_ack_frame(self, packet_space: str) -> QuicAckFrame:
        state = self._space_state(packet_space)
        if not state.received_packets:
            raise ProtocolError('no packets available to acknowledge')
        ordered = sorted(state.received_packets, reverse=True)
        ranges: list[tuple[int, int]] = []
        range_high = ordered[0]
        range_low = ordered[0]
        for packet_number in ordered[1:]:
            if packet_number == range_low - 1:
                range_low = packet_number
                continue
            ranges.append((range_low, range_high))
            range_high = packet_number
            range_low = packet_number
        ranges.append((range_low, range_high))
        largest_acked = ranges[0][1]
        first_ack_range = ranges[0][1] - ranges[0][0]
        ack_ranges: list[tuple[int, int]] = []
        previous_low = ranges[0][0]
        for range_low, range_high in ranges[1:]:
            gap = previous_low - range_high - 2
            ack_ranges.append((gap, range_high - range_low))
            previous_low = range_low
        local_ack_delay_exponent = self.local_transport_parameters.ack_delay_exponent if self.local_transport_parameters is not None else 3
        received_at = state.received_packet_times.get(largest_acked)
        ack_delay = 0
        if received_at is not None:
            delay_us = max(int((time.monotonic() - received_at) * 1_000_000), 0)
            ack_delay = delay_us // (1 << local_ack_delay_exponent)
        return QuicAckFrame(
            largest_acked=largest_acked,
            ack_delay=ack_delay,
            first_ack_range=first_ack_range,
            ack_ranges=ack_ranges,
        )

    def _parse_runtime_packet(self, data: bytes) -> tuple[Any, int, str]:
        if not data:
            raise ProtocolError('QUIC packet underflow')
        first_byte = data[0]
        if first_byte & 0x80:
            packet = decode_packet(data)
            if isinstance(packet, (QuicVersionNegotiationPacket, QuicRetryPacket, QuicStatelessResetPacket)):
                return packet, -1, PACKET_SPACE_INITIAL
            offset = 5
            dcid_len = data[offset]
            offset += 1 + dcid_len
            scid_len = data[offset]
            offset += 1 + scid_len
            packet_space = PACKET_SPACE_INITIAL
            if packet.packet_type == QuicLongHeaderType.INITIAL:
                token_length, offset = decode_quic_varint(data, offset)
                offset += token_length
                packet_space = PACKET_SPACE_INITIAL
            elif packet.packet_type == QuicLongHeaderType.HANDSHAKE:
                packet_space = PACKET_SPACE_HANDSHAKE
            elif packet.packet_type == QuicLongHeaderType.ZERO_RTT:
                packet_space = PACKET_SPACE_ZERO_RTT
            _payload_length, offset = decode_quic_varint(data, offset)
            return packet, offset, packet_space
        packet = decode_packet(data, destination_connection_id_length=max(len(self.local_cid), 1))
        return packet, 1 + len(packet.destination_connection_id), PACKET_SPACE_APPLICATION

    def _unprotect_short_packet(self, data: bytes, *, pn_offset: int) -> tuple[int, bytes, int]:
        current_keys = self._recv_1rtt_keys
        largest = self._space_state(PACKET_SPACE_APPLICATION).largest_received
        try:
            header, packet_number, plaintext = unprotect_quic_packet(
                data,
                pn_offset=pn_offset,
                keys=current_keys,
                largest_pn=largest,
            )
            observed_phase = 1 if (header[0] & 0x04) else 0
            if observed_phase != self._recv_key_phase:
                hash_name = self._tls_hash_name()
                updated_client_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
                updated_server_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
                candidate_recv_keys = self._derive_tls_packet_protection_keys(
                    updated_server_secret if self.is_client else updated_client_secret,
                    stage='application',
                )
                header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=candidate_recv_keys,
                    largest_pn=largest,
                )
                self._client_application_secret = updated_client_secret
                self._server_application_secret = updated_server_secret
                self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
                self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')
                self._recv_key_phase = observed_phase
                self._send_key_phase = observed_phase
            return packet_number, plaintext, observed_phase
        except ProtocolError:
            hash_name = self._tls_hash_name()
            updated_client_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
            updated_server_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
            candidate_recv_keys = self._derive_tls_packet_protection_keys(
                updated_server_secret if self.is_client else updated_client_secret,
                stage='application',
            )
            header, packet_number, plaintext = unprotect_quic_packet(
                data,
                pn_offset=pn_offset,
                keys=candidate_recv_keys,
                largest_pn=largest,
            )
            self._client_application_secret = updated_client_secret
            self._server_application_secret = updated_server_secret
            self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
            self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')
            self._recv_key_phase = 1 if (header[0] & 0x04) else 0
            self._send_key_phase = self._recv_key_phase
            return packet_number, plaintext, self._recv_key_phase

    def _decode_payload(self, data: bytes) -> tuple[Any, str, int, bytes]:
        packet, pn_offset, packet_space = self._parse_runtime_packet(data)
        if isinstance(packet, QuicVersionNegotiationPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicRetryPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicStatelessResetPacket):
            return packet, packet_space, -1, b''
        if isinstance(packet, QuicLongHeaderPacket):
            if packet.packet_type == QuicLongHeaderType.INITIAL:
                client_keys, server_keys = self._recv_initial_keys(packet)
                recv_keys = server_keys if self.is_client else client_keys
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=recv_keys,
                    largest_pn=self._space_state(PACKET_SPACE_INITIAL).largest_received,
                )
                return packet, PACKET_SPACE_INITIAL, packet_number, plaintext
            if packet.packet_type == QuicLongHeaderType.HANDSHAKE:
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=self._recv_handshake_keys(),
                    largest_pn=self._space_state(PACKET_SPACE_HANDSHAKE).largest_received,
                )
                return packet, PACKET_SPACE_HANDSHAKE, packet_number, plaintext
            if packet.packet_type == QuicLongHeaderType.ZERO_RTT:
                if self.is_client:
                    raise ProtocolError('clients must not receive 0-RTT packets')
                _header, packet_number, plaintext = unprotect_quic_packet(
                    data,
                    pn_offset=pn_offset,
                    keys=self._recv_0rtt_keys(),
                    largest_pn=self._space_state(PACKET_SPACE_APPLICATION).largest_received,
                )
                return packet, PACKET_SPACE_ZERO_RTT, packet_number, plaintext
            raise ProtocolError('unsupported QUIC long-header packet type')
        if isinstance(packet, QuicShortHeaderPacket):
            errors: list[Exception] = []
            for cid_length in self._short_header_destination_connection_id_lengths():
                try:
                    candidate = decode_packet(data, destination_connection_id_length=cid_length)
                    if not isinstance(candidate, QuicShortHeaderPacket):
                        continue
                    packet_number, plaintext, _key_phase = self._unprotect_short_packet(data, pn_offset=candidate.pn_offset)
                    return candidate, PACKET_SPACE_APPLICATION, packet_number, plaintext
                except ProtocolError as exc:
                    errors.append(exc)
                    continue
            raise ProtocolError(str(errors[-1]) if errors else 'failed to decode QUIC short-header packet')
        raise ProtocolError('unsupported QUIC packet')

    def _known_stateless_reset_tokens(self) -> set[bytes]:
        tokens = {token for _sequence, (_cid, token) in self.peer_connection_ids.items()}
        if self.peer_transport_parameters and self.peer_transport_parameters.stateless_reset_token is not None:
            tokens.add(self.peer_transport_parameters.stateless_reset_token)
        return tokens

    def _maybe_stateless_reset(self, data: bytes) -> QuicStatelessResetPacket | None:
        if len(data) < 21:
            return None
        token = data[-16:]
        if token not in self._known_stateless_reset_tokens():
            return None
        return QuicStatelessResetPacket(stateless_reset_token=token, unpredictable_bits=data[:-16])

    def _observe_path(self, addr: tuple[str, int] | None) -> QuicEvent | None:
        if addr is None:
            return None
        if self._path_addr is None:
            self._path_addr = addr
            self._activate_path(self._path_key_for_addr(addr))
            return None
        if self._path_addr == addr:
            self._activate_path(self._path_key_for_addr(addr))
            return None
        if self.local_transport_parameters and self.local_transport_parameters.disable_active_migration and self.address_validated:
            raise ProtocolError('peer changed address despite disable_active_migration')
        previous = self._path_addr
        self._path_addr = addr
        self._activate_path(self._path_key_for_addr(addr))
        return QuicEvent(kind='path_migrated', detail={'from': previous, 'to': addr})

    def _short_header_destination_connection_id_lengths(self) -> tuple[int, ...]:
        lengths: list[int] = []
        for candidate in (
            self.local_cid,
            self.remote_cid,
            *(cid for cid, _token in self.issued_connection_ids.values()),
            *(cid for cid, _token in self.peer_connection_ids.values()),
        ):
            if candidate:
                length = len(candidate)
                if 1 <= length <= 20 and length not in lengths:
                    lengths.append(length)
        if not lengths:
            lengths.append(1)
        return tuple(lengths)

    def _peek_packet(self, data: bytes) -> Any:
        if not data:
            raise ProtocolError('QUIC packet underflow')
        if data[0] & 0x80:
            return decode_packet(data)
        return decode_packet(data, destination_connection_id_length=self._short_header_destination_connection_id_lengths()[0])
