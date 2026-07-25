from __future__ import annotations

from .imports import *

class HTTP3WebTransportSupportMixin:
    def _webtransport_settings_received(self, session: HTTP3Session) -> bool:
        stream_id = session.h3.state.remote_control_stream_id
        if stream_id is None:
            return False
        state = session.h3.state.uni_streams.get(stream_id)
        return bool(state and state.settings_received)

    def _is_configured_webtransport_token(self, token: bytes) -> bool:
        max_sessions = int(self.config.webtransport.max_sessions or 1)
        return any(
            profile_spec(name, max_sessions=max_sessions).connect_token == token
            for name in self.config.webtransport.profiles
        )

    def _ensure_webtransport_negotiation(self, session: HTTP3Session):
        if session.webtransport_negotiation_frozen:
            return session.webtransport_negotiation
        if not self._webtransport_settings_received(session):
            return None
        result = negotiate_profiles(
            self.config.webtransport.profiles,
            self.config.webtransport.preferred_profile or self.config.webtransport.profiles[0],
            session.h3.state.remote_settings,
            max_sessions=int(self.config.webtransport.max_sessions or 1),
        )
        session.webtransport_negotiation = result
        session.webtransport_negotiation_frozen = True
        if self.metrics is not None:
            if result.selected_profile is not None:
                self.metrics.webtransport_profile_selected(result.selected_profile)
            else:
                self.metrics.webtransport_negotiation_rejected_observed()
        self.trace_webtransport(
            'webtransport.profile.selected' if result.selected_profile else 'webtransport.profile.rejected',
            **self._trace_session_fields(session),
            configured_profiles=list(result.configured_profiles),
            advertised_codepoints=[f'{value:#x}' for value in result.advertised_codepoints],
            peer_profiles=list(result.peer_profiles),
            mutual_profiles=list(result.mutual_profiles),
            preferred_profile=result.preferred_profile,
            selected_profile=result.selected_profile,
            failure_reason=result.failure_reason,
        )
        if self.connection_inventory is not None:
            self.connection_inventory.update_connection(
                self._connection_id_for_session(session),
                security={
                    'webtransport_profile': result.selected_profile,
                    'webtransport_setting': (
                        f'{profile_spec(result.selected_profile).setting_codepoint:#x}'
                        if result.selected_profile else None
                    ),
                },
            )
        return result

    async def _admit_webtransport_connect(
        self, session, stream_id, request_state, header_map, endpoint
    ) -> list[bytes]:
        negotiation = self._ensure_webtransport_negotiation(session)
        if negotiation is None:
            target = self._request_target_from_header_map(header_map)
            self.trace_webtransport(
                'webtransport.connect.rejected',
                **self._trace_session_fields(session),
                failure_reason='settings-not-received',
            )
            self.access_logger.log_http(session.addr, 'CONNECT', target, 425, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session, stream_id, 425, [(b'content-type', b'text/plain')],
                b'webtransport negotiation incomplete', end_stream=True,
            )
        if negotiation.selected_profile is None:
            target = self._request_target_from_header_map(header_map)
            self.trace_webtransport(
                'webtransport.connect.rejected',
                **self._trace_session_fields(session),
                failure_reason=negotiation.failure_reason,
            )
            self.access_logger.log_http(session.addr, 'CONNECT', target, 421, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session, stream_id, 421, [(b'content-type', b'text/plain')],
                b'no mutually supported webtransport profile', end_stream=True,
            )
        profile = profile_spec(
            negotiation.selected_profile,
            max_sessions=int(self.config.webtransport.max_sessions or 1),
        )
        if header_map.get(b':protocol') != profile.connect_token:
            target = self._request_target_from_header_map(header_map)
            self.trace_webtransport(
                'webtransport.connect.rejected',
                **self._trace_session_fields(session),
                selected_profile=profile.profile.value,
                failure_reason='connect-token-mismatch',
            )
            self.access_logger.log_http(session.addr, 'CONNECT', target, 501, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session, stream_id, 501, [(b'content-type', b'text/plain')],
                b'webtransport profile token mismatch', end_stream=True,
            )
        peer = session.quic.peer_transport_parameters
        missing = missing_peer_requirement(
            profile,
            session.h3.state.remote_settings,
            max_datagram_frame_size=(peer.max_datagram_frame_size if peer else None),
            reset_stream_at=bool(peer and peer.reset_stream_at),
        )
        if missing is None:
            missing = missing_request_requirement(profile, header_map)
        if missing is None:
            conflict = conflicting_request_profile(
                profile,
                header_map,
                tuple(
                    profile_spec(name, max_sessions=int(self.config.webtransport.max_sessions or 1))
                    for name in self.config.webtransport.profiles
                ),
            )
            if conflict is not None:
                missing = f'header-profile:{conflict}'
        if missing is None:
            return await self._start_webtransport_stream_locked(
                session, stream_id, request_state, header_map, endpoint
            )
        target = self._request_target_from_header_map(header_map)
        self.trace_webtransport(
            'webtransport.connection.requirement_missing',
            **self._trace_session_fields(session),
            profile=profile.profile.value,
            requirement=missing,
        )
        self.access_logger.log_http(session.addr, 'CONNECT', target, 421, 'HTTP/3')
        return self._build_http3_response_datagrams_locked(
            session, stream_id, 421, [(b'content-type', b'text/plain')],
            b'webtransport requirements not met', end_stream=True,
        )

    def _webtransport_max_datagram_size(self) -> int:
        # Keep the public config path discoverable for SSOT proof checks: webtransport.max_datagram_size.
        configured = self.config.webtransport.max_datagram_size
        return int(configured if configured is not None else self.listener.max_datagram_size)

    def _webtransport_security_extension(self, session: HTTP3Session) -> dict[str, object]:
        handshake = session.quic.handshake_driver
        peer_certificate = getattr(handshake, 'peer_certificate_pem', None)
        return {
            'alpn': getattr(handshake, 'selected_alpn', None),
            'mtls': bool(peer_certificate),
            'peer_certificate': peer_certificate,
            'sni': getattr(handshake, 'server_name', None),
            'tls': bool(self.listener.ssl_enabled and handshake is not None and getattr(handshake, 'complete', False)),
        }

    def _webtransport_transport_extension(self, session: HTTP3Session) -> dict[str, object]:
        return {
            'address_validated': bool(session.address_validated or session.quic.address_validated),
            'connection_id': session.quic.local_cid.hex(),
            'max_datagram_size': self._webtransport_max_datagram_size(),
            'retry_required': bool(self.listener.quic_require_retry),
        }

    def _encode_webtransport_datagram_payload(self, stream_id: int, data: bytes) -> bytes:
        if len(data) > self._webtransport_max_datagram_size():
            raise ProtocolError('webtransport.max_datagram_size exceeded')
        quarter_stream_id = stream_id // 4
        return encode_quic_varint(quarter_stream_id) + data

    def _decode_webtransport_datagram_payload(self, payload: bytes) -> tuple[int, bytes]:
        quarter_stream_id, offset = decode_quic_varint(payload, 0)
        return int(quarter_stream_id) * 4, payload[offset:]

    def _stream_is_client_initiated_bidi(self, stream_id: int) -> bool:
        return (stream_id & 0x03) == 0x00

    def _stream_is_server_initiated_bidi(self, stream_id: int) -> bool:
        return (stream_id & 0x03) == 0x01

    def _stream_is_client_initiated_unidi(self, stream_id: int) -> bool:
        return (stream_id & 0x03) == 0x02

    def _parse_webtransport_bidi_stream_prefix(self, payload: bytes) -> tuple[int, int, bytes] | None:
        try:
            signal, offset = decode_quic_varint(payload, 0)
        except ValueError:
            return None
        if signal != self._WEBTRANSPORT_BIDI_STREAM_SIGNAL:
            return (-1, -1, payload)
        try:
            session_id, offset = decode_quic_varint(payload, offset)
        except ValueError:
            return None
        return signal, session_id, payload[offset:]
    async def _abort_session_webtransports(self, session: HTTP3Session) -> None:
        session_ids = [webtransport.session_id for webtransport in session.webtransport_sessions.values()]
        for webtransport in list(session.webtransport_sessions.values()):
            with suppress(Exception):
                await webtransport.abort()
        session.webtransport_sessions.clear()
        session.webtransport_streams.clear()
        session.webtransport_stream_owners.clear()
        session.webtransport_stream_prefaces.clear()
        session.webtransport_server_prefaced_streams.clear()
        for session_id in session_ids:
            if self.connection_inventory is not None:
                self.connection_inventory.close_session(session_id, reason='abort-session')
            self._webtransport_release_session(session_id, reason='abort-session')
            self.trace_webtransport(
                'webtransport.session.cleanup',
                **self._trace_session_fields(session),
                session_id=session_id,
                reason='abort-session',
            )

    def _release_stream_work_lease(self, session: HTTP3Session, stream_id: int) -> None:
        lease = session.stream_work_leases.pop(stream_id, None)
        if lease is not None:
            lease.release()

    def _on_websocket_stream_closed(self, session: HTTP3Session, stream_id: int) -> None:
        session.websocket_sessions.pop(stream_id, None)
        if self.connection_inventory is not None:
            self.connection_inventory.close_session(
                f"{self._connection_id_for_session(session)}:websocket:{stream_id}",
                reason='websocket-closed',
            )
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)

    def _on_webtransport_stream_closed(self, session: HTTP3Session, stream_id: int) -> None:
        webtransport = session.webtransport_sessions.pop(stream_id, None)
        session.webtransport_streams.discard(stream_id)
        session.webtransport_stream_owners.pop(stream_id, None)
        session.webtransport_stream_prefaces.pop(stream_id, None)
        session.webtransport_server_prefaced_streams.discard(stream_id)
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)
        if webtransport is not None:
            if self.connection_inventory is not None:
                self.connection_inventory.close_session(webtransport.session_id, reason='stream-closed')
            self._webtransport_release_session(webtransport.session_id, reason='stream-closed')
            self.trace_webtransport(
                'webtransport.session.cleanup',
                **self._trace_session_fields(session),
                session_id=webtransport.session_id,
                stream_id=stream_id,
                reason='stream-closed',
            )
