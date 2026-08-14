from __future__ import annotations

from .imports import *

class QuicConnectionBaseMixin:
    @property
    def retry_source_connection_id(self) -> bytes | None:
        return self._retry_source_connection_id

    @property
    def peer_new_tokens(self) -> tuple[bytes, ...]:
        return tuple(self._peer_new_tokens)

    @property
    def peer_preferred_address(self) -> bytes | None:
        return self._peer_preferred_address

    @property
    def _send_1rtt_keys(self) -> QuicPacketProtectionKeys:
        return self.client_1rtt_keys if self.is_client else self.server_1rtt_keys

    @property
    def _recv_1rtt_keys(self) -> QuicPacketProtectionKeys:
        return self.server_1rtt_keys if self.is_client else self.client_1rtt_keys

    def _space_state(self, packet_space: str) -> _PacketSpaceState:
        normalized = PACKET_SPACE_APPLICATION if packet_space == PACKET_SPACE_ZERO_RTT else packet_space
        if normalized not in self._packet_spaces:
            self._packet_spaces[normalized] = _PacketSpaceState(name=normalized)
        return self._packet_spaces[normalized]

    def _recovery_space(self, packet_space: str) -> str:
        return PACKET_SPACE_APPLICATION if packet_space == PACKET_SPACE_ZERO_RTT else packet_space

    def _path_key_for_addr(self, addr: tuple[str, int] | None) -> Any:
        return _DEFAULT_PATH_KEY if addr is None else addr

    def _path_state(self, path_key: Any) -> _PathRuntime:
        state = self._path_states.get(path_key)
        if state is None:
            addr = None if path_key == _DEFAULT_PATH_KEY else path_key
            path_budget = min(
                self.configured_max_datagram_size,
                self.peer_max_udp_payload_size or self.configured_max_datagram_size,
            )
            state = _PathRuntime(
                key=path_key,
                addr=addr,
                recovery=QuicLossRecovery(
                    max_datagram_size=path_budget,
                    congestion_controller_factory=self._congestion_controller_factory,
                    congestion_controller_options=self._congestion_controller_options,
                    congestion_controller_options_validated=True,
                    clock=self._congestion_clock,
                ),
                max_udp_payload_size=path_budget,
            )
            if self.peer_transport_parameters is not None:
                state.recovery.rtt.max_ack_delay = self.recovery.rtt.max_ack_delay
            self._path_states[path_key] = state
        return state

    def _effective_send_datagram_size(self, path_key: Any | None = None) -> int:
        selected = self._active_path_key if path_key is None else path_key
        path = self._path_state(selected)
        return min(
            self.configured_max_datagram_size,
            self.peer_max_udp_payload_size or self.configured_max_datagram_size,
            path.max_udp_payload_size,
        )

    def _activate_path(self, path_key: Any) -> _PathRuntime:
        state = self._path_state(path_key)
        self._active_path_key = path_key
        self.recovery = state.recovery
        self.congestion.bytes_in_flight = self.recovery.bytes_in_flight
        self.congestion.congestion_window = self.recovery.congestion_window
        self.congestion.ssthresh = self.recovery.ssthresh
        return state

    def _refresh_congestion_snapshot(self, recovery: QuicLossRecovery | None = None) -> None:
        target = self.recovery if recovery is None else recovery
        if target is self.recovery:
            self.congestion.bytes_in_flight = target.bytes_in_flight
            self.congestion.congestion_window = target.congestion_window
            self.congestion.ssthresh = target.ssthresh

    def _register_datagram_packets(self, datagram: bytes, packet_refs: list[tuple[str, int]]) -> None:
        if packet_refs:
            self._wire_datagram_packets[datagram] = list(packet_refs)

    def _packet_refs_for_datagram(self, datagram: bytes) -> list[tuple[str, int]]:
        refs = self._wire_datagram_packets.get(datagram)
        if refs is not None:
            return list(refs)
        try:
            packets = split_coalesced_packets(datagram, destination_connection_id_length=max(len(self.local_cid), 1))
        except ProtocolError:
            return []
        resolved: list[tuple[str, int]] = []
        for packet in packets:
            packet_refs = self._wire_datagram_packets.get(packet)
            if packet_refs is None:
                continue
            resolved.extend(packet_refs)
        if resolved:
            self._wire_datagram_packets[datagram] = list(resolved)
        return resolved

    def _sync_packet_number_snapshot(self) -> None:
        self.packet_numbers.initial_send = self._packet_spaces[PACKET_SPACE_INITIAL].send
        self.packet_numbers.handshake_send = self._packet_spaces[PACKET_SPACE_HANDSHAKE].send
        self.packet_numbers.application_send = self._packet_spaces[PACKET_SPACE_APPLICATION].send
        self.packet_numbers.initial_largest_received = self._packet_spaces[PACKET_SPACE_INITIAL].largest_received
        self.packet_numbers.handshake_largest_received = self._packet_spaces[PACKET_SPACE_HANDSHAKE].largest_received
        self.packet_numbers.application_largest_received = self._packet_spaces[PACKET_SPACE_APPLICATION].largest_received

    def _issue_address_token(
        self,
        *,
        purpose: int,
        addr: tuple[str, int] | None,
        original_destination_connection_id: bytes = b'',
        retry_source_connection_id: bytes = b'',
    ) -> bytes:
        address_bytes = _serialize_address((addr[0], 0) if addr is not None else None)
        if len(original_destination_connection_id) > 255 or len(retry_source_connection_id) > 255:
            raise ValueError('connection ids are too large to encode in a QUIC token')
        body = bytearray()
        body.append(_TOKEN_FORMAT_VERSION)
        body.append(purpose)
        body.extend(_current_time_ms().to_bytes(8, 'big'))
        body.extend(len(address_bytes).to_bytes(2, 'big'))
        body.extend(address_bytes)
        body.append(len(original_destination_connection_id))
        body.extend(original_destination_connection_id)
        body.append(len(retry_source_connection_id))
        body.extend(retry_source_connection_id)
        mac = hmac.new(self._token_secret, bytes(body), hashlib.sha256).digest()[:_TOKEN_MAC_LENGTH]
        return bytes(body) + mac

    def _validate_address_token(
        self,
        token: bytes,
        *,
        addr: tuple[str, int] | None,
        expected_purpose: int | None = None,
    ) -> _TokenInfo | None:
        minimum = 1 + 1 + 8 + 2 + 1 + 1 + _TOKEN_MAC_LENGTH
        if len(token) < minimum:
            return None
        body, mac = token[:-_TOKEN_MAC_LENGTH], token[-_TOKEN_MAC_LENGTH:]
        expected_mac = hmac.new(self._token_secret, body, hashlib.sha256).digest()[:_TOKEN_MAC_LENGTH]
        if not hmac.compare_digest(mac, expected_mac):
            return None
        offset = 0
        format_version = body[offset]
        offset += 1
        if format_version != _TOKEN_FORMAT_VERSION:
            return None
        purpose = body[offset]
        offset += 1
        if expected_purpose is not None and purpose != expected_purpose:
            return None
        if offset + 8 > len(body):
            return None
        issued_at_ms = int.from_bytes(body[offset:offset + 8], 'big')
        offset += 8
        if offset + 2 > len(body):
            return None
        address_length = int.from_bytes(body[offset:offset + 2], 'big')
        offset += 2
        end = offset + address_length
        if end > len(body):
            return None
        address_bytes = body[offset:end]
        offset = end
        if offset >= len(body):
            return None
        original_length = body[offset]
        offset += 1
        end = offset + original_length
        if end > len(body):
            return None
        original_destination_connection_id = body[offset:end]
        offset = end
        if offset >= len(body):
            return None
        retry_length = body[offset]
        offset += 1
        end = offset + retry_length
        if end != len(body):
            return None
        retry_source_connection_id = body[offset:end]
        if addr is not None and address_bytes:
            try:
                token_address = _parse_serialized_address(address_bytes)
            except ProtocolError:
                return None
            if token_address[0] != addr[0] or token_address[1] not in {0, addr[1]}:
                return None
        now_ms = _current_time_ms()
        if issued_at_ms > now_ms + 60_000:
            return None
        lifetime_ms = self.retry_token_lifetime_ms if purpose == _TOKEN_PURPOSE_RETRY else self.new_token_lifetime_ms
        if now_ms - issued_at_ms > lifetime_ms:
            return None
        address = _parse_serialized_address(address_bytes) if address_bytes else None
        return _TokenInfo(
            purpose=purpose,
            issued_at_ms=issued_at_ms,
            address=address,
            original_destination_connection_id=original_destination_connection_id,
            retry_source_connection_id=retry_source_connection_id,
        )

    def _update_local_transport_parameters(self) -> None:
        if self.handshake_driver is None:
            return
        transport_parameters = self.handshake_driver.transport_parameters
        transport_parameters.initial_source_connection_id = self.local_cid
        if self.is_client:
            transport_parameters.original_destination_connection_id = None
            transport_parameters.preferred_address = None
            transport_parameters.retry_source_connection_id = None
            transport_parameters.stateless_reset_token = None
        else:
            if transport_parameters.stateless_reset_token is None:
                transport_parameters.stateless_reset_token = derive_secret(self.local_cid + self.secret, b'stateless-reset', length=16)
            if self._original_destination_connection_id is not None:
                transport_parameters.original_destination_connection_id = self._original_destination_connection_id
            if self._retry_source_connection_id is not None:
                transport_parameters.retry_source_connection_id = self._retry_source_connection_id
        self.local_transport_parameters = transport_parameters
        self.streams.configure_local_initial_limits(
            bidirectional=transport_parameters.max_streams_bidi,
            unidirectional=transport_parameters.max_streams_uni,
        )
        self.flow.configure_local_initial_limits(
            max_data=transport_parameters.max_data,
            max_stream_data_bidi_local=transport_parameters.max_stream_data_bidi_local,
            max_stream_data_bidi_remote=transport_parameters.max_stream_data_bidi_remote,
            max_stream_data_uni=transport_parameters.max_stream_data_uni,
        )

    def _derive_tls_packet_protection_keys(self, secret: bytes, *, stage: str) -> QuicPacketProtectionKeys:
        if self.handshake_driver is None:
            return derive_quic_packet_protection_keys(secret)
        parameters = self.handshake_driver.packet_protection_parameters(stage=stage)
        return derive_quic_packet_protection_keys(
            secret,
            key_length=parameters.key_length,
            iv_length=parameters.iv_length,
            hp_length=parameters.hp_length,
            hash_name=parameters.hash_name,
        )

    def _tls_hash_name(self) -> str:
        if self.handshake_driver is None:
            return 'sha256'
        return self.handshake_driver.cipher_parameters.hash_name

    def _refresh_tls_key_material(self) -> None:
        if self.handshake_driver is None:
            return
        self._update_local_transport_parameters()
        client_early_secret = getattr(self.handshake_driver, '_client_early_secret', None)
        if client_early_secret is not None and self.client_0rtt_keys is None:
            self.client_0rtt_keys = self._derive_tls_packet_protection_keys(client_early_secret, stage='0rtt')
        client_handshake_secret = getattr(self.handshake_driver, '_client_handshake_secret', None)
        server_handshake_secret = getattr(self.handshake_driver, '_server_handshake_secret', None)
        if client_handshake_secret is not None and server_handshake_secret is not None and not self._handshake_traffic_installed:
            self._client_handshake_secret = client_handshake_secret
            self._server_handshake_secret = server_handshake_secret
            self.client_handshake_keys = self._derive_tls_packet_protection_keys(client_handshake_secret, stage='handshake')
            self.server_handshake_keys = self._derive_tls_packet_protection_keys(server_handshake_secret, stage='handshake')
            self._handshake_traffic_installed = True
        traffic_secrets = self.handshake_driver.traffic_secrets
        if traffic_secrets is None or self._application_traffic_installed:
            return
        self._client_handshake_secret = traffic_secrets.client_handshake_secret
        self._server_handshake_secret = traffic_secrets.server_handshake_secret
        self.client_handshake_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_handshake_secret, stage='handshake')
        self.server_handshake_keys = self._derive_tls_packet_protection_keys(traffic_secrets.server_handshake_secret, stage='handshake')
        if traffic_secrets.client_early_secret is not None:
            self.client_0rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_early_secret, stage='0rtt')
        self._client_application_secret = traffic_secrets.client_application_secret
        self._server_application_secret = traffic_secrets.server_application_secret
        self.client_1rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.client_application_secret, stage='application')
        self.server_1rtt_keys = self._derive_tls_packet_protection_keys(traffic_secrets.server_application_secret, stage='application')
        self._application_traffic_installed = True

    def _apply_peer_transport_parameters(self) -> None:
        if self.handshake_driver is None or self.handshake_driver.peer_transport_parameters is None:
            return
        peer = self.handshake_driver.peer_transport_parameters
        if self.is_client:
            if self._original_destination_connection_id is not None and peer.original_destination_connection_id != self._original_destination_connection_id:
                raise ProtocolError('server original_destination_connection_id transport parameter mismatch')
            if self._first_server_source_connection_id is not None and peer.initial_source_connection_id != self._first_server_source_connection_id:
                raise ProtocolError('server initial_source_connection_id transport parameter mismatch')
            if self._received_retry:
                if peer.retry_source_connection_id != self._retry_source_connection_id:
                    raise ProtocolError('server retry_source_connection_id transport parameter mismatch')
            elif peer.retry_source_connection_id is not None:
                raise ProtocolError('server sent retry_source_connection_id without using Retry')
        else:
            if peer.original_destination_connection_id is not None:
                raise ProtocolError('client sent forbidden original_destination_connection_id transport parameter')
            if peer.preferred_address is not None:
                raise ProtocolError('client sent forbidden preferred_address transport parameter')
            if peer.retry_source_connection_id is not None:
                raise ProtocolError('client sent forbidden retry_source_connection_id transport parameter')
            if peer.stateless_reset_token is not None:
                raise ProtocolError('client sent forbidden stateless_reset_token transport parameter')
            if self._peer_initial_source_connection_id is not None and peer.initial_source_connection_id != self._peer_initial_source_connection_id:
                raise ProtocolError('client initial_source_connection_id transport parameter mismatch')
        self.peer_transport_parameters = peer
        self.peer_max_udp_payload_size = max(int(peer.max_udp_payload_size), _MIN_INITIAL_DATAGRAM_SIZE)
        self.max_datagram_size = min(self.configured_max_datagram_size, self.peer_max_udp_payload_size)
        for path in self._path_states.values():
            path.max_udp_payload_size = min(path.max_udp_payload_size, self.max_datagram_size)
            path.recovery.update_max_datagram_size(path.max_udp_payload_size)
        self.local_transport_parameters = self.handshake_driver.transport_parameters
        ack_delay_exponent = peer.ack_delay_exponent if peer.ack_delay_exponent >= 0 else 3
        max_ack_delay = max(peer.max_ack_delay, 0) / 1000.0
        for path in self._path_states.values():
            path.recovery.rtt.max_ack_delay = max_ack_delay
        self._peer_active_connection_id_limit = peer.active_connection_id_limit
        self._peer_default_stream_window = peer.max_stream_data_bidi_remote
        self.flow.configure_peer_initial_limits(
            max_data=peer.max_data,
            max_stream_data_bidi_local=peer.max_stream_data_bidi_local,
            max_stream_data_bidi_remote=peer.max_stream_data_bidi_remote,
            max_stream_data_uni=peer.max_stream_data_uni,
        )
        self.streams.configure_peer_initial_limits(
            bidirectional=peer.max_streams_bidi,
            unidirectional=peer.max_streams_uni,
        )
        self._peer_preferred_address = peer.preferred_address
        self._ack_delay_exponent = ack_delay_exponent
        self._update_runtime_timers()

    def _initial_keys(self, *, destination_connection_id: bytes | None = None) -> tuple[QuicPacketProtectionKeys, QuicPacketProtectionKeys]:
        if destination_connection_id is not None:
            connection_id = destination_connection_id
        elif self.is_client:
            connection_id = self.remote_cid or self._original_destination_connection_id or self.local_cid
        else:
            connection_id = self._retry_source_connection_id or self.local_cid or self._original_destination_connection_id or self.remote_cid
        return derive_initial_packet_protection_keys(connection_id)

    def _recv_initial_keys(self, packet: QuicLongHeaderPacket) -> tuple[QuicPacketProtectionKeys, QuicPacketProtectionKeys]:
        if self.is_client:
            connection_id = self.remote_cid or self._retry_source_connection_id or self._original_destination_connection_id or packet.source_connection_id
        else:
            connection_id = packet.destination_connection_id
        return derive_initial_packet_protection_keys(connection_id)

    def _send_handshake_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        keys = self.client_handshake_keys if self.is_client else self.server_handshake_keys
        if keys is None:
            raise ProtocolError('handshake packet protection keys are not available')
        return keys

    def _recv_handshake_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        keys = self.server_handshake_keys if self.is_client else self.client_handshake_keys
        if keys is None:
            raise ProtocolError('handshake packet protection keys are not available')
        return keys

    def _send_0rtt_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        if not self.is_client:
            raise ProtocolError('only clients can send 0-RTT packets')
        if self.client_0rtt_keys is None:
            raise ProtocolError('0-RTT packet protection keys are not available')
        return self.client_0rtt_keys

    def _recv_0rtt_keys(self) -> QuicPacketProtectionKeys:
        self._refresh_tls_key_material()
        if self.client_0rtt_keys is None:
            raise ProtocolError('0-RTT packet protection keys are not available')
        return self.client_0rtt_keys

    def _promote_key_update(self) -> None:
        hash_name = self._tls_hash_name()
        self._client_application_secret = update_quic_secret(self._client_application_secret, hash_name=hash_name)
        self._server_application_secret = update_quic_secret(self._server_application_secret, hash_name=hash_name)
        self.client_1rtt_keys = self._derive_tls_packet_protection_keys(self._client_application_secret, stage='application')
        self.server_1rtt_keys = self._derive_tls_packet_protection_keys(self._server_application_secret, stage='application')

    def initiate_key_update(self) -> None:
        self._promote_key_update()
        self._send_key_phase ^= 1
        self._recv_key_phase = self._send_key_phase
