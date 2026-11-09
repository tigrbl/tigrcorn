from __future__ import annotations

from .imports import *

class HTTP3LifecycleMixin:
    def trace_webtransport(self, event: str, **fields: object) -> None:
        entry: dict[str, object] = {'event': event}
        for key, value in fields.items():
            if value is not None:
                entry[key] = value
        self.webtransport_trace.append(entry)

    def _trace_session_fields(self, session: HTTP3Session | None = None) -> dict[str, object]:
        if session is None:
            return {}
        return {
            'addr': f'{session.addr[0]}:{session.addr[1]}',
            'h3_session_id': session.runtime_id,
            'local_cid': session.quic.local_cid.hex(),
            'remote_cid': session.quic.remote_cid.hex() if isinstance(session.quic.remote_cid, bytes) else None,
            'state': session.quic.state,
        }

    @staticmethod
    def _webtransport_address(addr: tuple[str, int]) -> str:
        return f"{addr[0]}:{addr[1]}"

    def _connection_id_for_session(self, session: HTTP3Session) -> str:
        return f"conn:h3:{session.runtime_id or session.quic.local_cid.hex() or 'session'}"

    def _listener_id(self) -> str:
        return self.listener.label or f"{self.listener.kind}:{self.listener.host}:{self.listener.port}"

    def _register_h3_connection(self, session: HTTP3Session) -> None:
        inventory = self.connection_inventory
        if inventory is None:
            return
        address = self._webtransport_address(session.addr)
        handshake = session.quic.handshake_driver
        inventory.open_connection(
            self._connection_id_for_session(session),
            transport='quic',
            protocols=tuple(sorted(self.listener.enabled_protocols)),
            listener_id=self._listener_id(),
            peer_id=peer_id_from_address(address),
            remote_address=address,
            local_address=self.listener.label,
            security={
                'alpn': getattr(handshake, 'selected_alpn', None) if handshake is not None else None,
                'local_cid': session.quic.local_cid.hex(),
                'remote_cid': session.quic.remote_cid.hex() if isinstance(session.quic.remote_cid, bytes) else None,
                'tls': bool(handshake is not None),
            },
        )

    def _update_h3_connection(self, session: HTTP3Session) -> None:
        inventory = self.connection_inventory
        if inventory is None:
            return
        inventory.update_connection(
            self._connection_id_for_session(session),
            remote_address=self._webtransport_address(session.addr),
            counters={
                'bytes_received': session.bytes_received,
                'bytes_sent': session.bytes_sent,
                'requests': len(session.responded_streams),
                'streams': len(session.h3.requests) + len(session.webtransport_streams),
                'webtransport_sessions': len(session.webtransport_sessions),
                'websocket_sessions': len(session.websocket_sessions),
            },
            security={
                'local_cid': session.quic.local_cid.hex(),
                'remote_cid': session.quic.remote_cid.hex() if isinstance(session.quic.remote_cid, bytes) else None,
            },
        )

    def _close_h3_connection(self, session: HTTP3Session, *, reason: str) -> None:
        inventory = self.connection_inventory
        if inventory is None:
            return
        self._update_h3_connection(session)
        inventory.close_connection(self._connection_id_for_session(session), reason=reason)

    def _webtransport_budget_snapshot(self) -> dict[str, Any] | None:
        manager = self.webtransport_governance
        if manager is None:
            return None
        return manager.snapshot()

    def _webtransport_register_session(self, session: HTTP3Session, webtransport: _HTTP3WebTransportSession) -> dict[str, Any] | None:
        manager = self.webtransport_governance
        if manager is None:
            return None
        return manager.open_session(
            webtransport.session_id,
            peer_id=peer_id_from_address(self._webtransport_address(session.addr)),
            address=self._webtransport_address(session.addr),
        )

    def _webtransport_register_stream(self, webtransport: _HTTP3WebTransportSession, stream_id: int | str) -> dict[str, Any] | None:
        if self.connection_inventory is not None:
            self.connection_inventory.update_session(
                webtransport.session_id,
                stream_ids=(str(stream_id),),
            )
        manager = self.webtransport_governance
        if manager is None:
            return None
        return manager.open_stream(webtransport.session_id, str(stream_id))

    def _webtransport_release_stream(
        self, webtransport: _HTTP3WebTransportSession, stream_id: int | str
    ) -> dict[str, Any] | None:
        manager = self.webtransport_governance
        if manager is None:
            return None
        return manager.close_stream(webtransport.session_id, str(stream_id))

    def _webtransport_register_datagram(
        self,
        webtransport: _HTTP3WebTransportSession,
        datagram_id: str,
        data: bytes,
    ) -> dict[str, Any] | None:
        manager = self.webtransport_governance
        if manager is None:
            return None
        return manager.send_datagram(webtransport.session_id, datagram_id, data)

    def _webtransport_register_rebinding(self, session: HTTP3Session) -> None:
        manager = self.webtransport_governance
        if manager is None:
            return
        new_address = self._webtransport_address(session.addr)
        for webtransport in session.webtransport_sessions.values():
            with suppress(WebTransportGovernanceError):
                manager.migrate_session(webtransport.session_id, new_address=new_address)

    def _webtransport_release_session(self, session_id: str, *, reason: str) -> dict[str, Any] | None:
        manager = self.webtransport_governance
        if manager is None:
            return None
        with suppress(WebTransportGovernanceError):
            return manager.close_session(session_id, reason=reason)
        return None

    def _assign_session_runtime_id(self, session: HTTP3Session) -> None:
        if session.runtime_id:
            return
        self._session_sequence += 1
        session.runtime_id = f'h3s-{self._session_sequence}'

    def _session_ticket_early_data_size(self, session: HTTP3Session) -> int:
        if session.quic.handshake_driver is None:
            return 0
        if self.config.quic.early_data_policy == 'deny':
            return 0
        return self._EARLY_DATA_TICKET_SIZE

    def _should_send_too_early(self, session: HTTP3Session) -> bool:
        handshake = session.quic.handshake_driver
        if handshake is None:
            return False
        if self.config.quic.early_data_policy != 'require':
            return False
        return bool(getattr(handshake, '_using_psk', False)) and not bool(getattr(handshake, 'early_data_accepted', False))

    def _configure_session_handshake(self, session: HTTP3Session) -> None:
        if not self.listener.ssl_enabled or session.quic.handshake_driver is not None:
            return
        context = build_server_ssl_context(self.listener)
        assert context is not None
        transport_parameters = TransportParameters(
            max_udp_payload_size=self.listener.max_datagram_size,
            max_streams_bidi=self.config.scheduler.max_streams or 128,
            max_streams_uni=self.config.scheduler.max_streams or 128,
            idle_timeout=int(self.config.quic.idle_timeout * 1000),
            max_datagram_frame_size=self.listener.max_datagram_size,
            reset_stream_at=(
                'webtransport' in self.listener.enabled_protocols
                and any(
                    profile_spec(name, max_sessions=int(self.config.webtransport.max_sessions or 1)).requires_reset_stream_at
                    for name in self.config.webtransport.profiles
                )
            ),
        )
        session.quic.configure_handshake(
            QuicTlsHandshakeDriver(
                is_client=False,
                alpn=tuple(self.listener.alpn_protocols or ('h3',)),
                server_name=self.listener.host or 'localhost',
                certificate_pem=context.certificate_pem,
                private_key_pem=context.private_key_pem,
                private_key_password=context.private_key_password,
                trusted_certificates=context.trusted_certificates,
                require_client_certificate=context.require_client_certificate,
                validation_policy=context.validation_policy,
                cipher_suites=context.cipher_suites,
                transport_parameters=transport_parameters,
                enable_early_data=self.config.quic.early_data_policy != 'deny',
            )
        )
