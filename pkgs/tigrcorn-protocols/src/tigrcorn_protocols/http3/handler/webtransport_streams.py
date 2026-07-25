from __future__ import annotations

from .imports import *
from .webtransport import _HTTP3WebTransportSession

class HTTP3WebTransportStreamsMixin:
    async def _consume_webtransport_stream_event_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        fin: bool,
    ) -> tuple[bool, bytes]:
        owner_stream_id = session.webtransport_stream_owners.get(stream_id)
        if owner_stream_id is not None and owner_stream_id != stream_id:
            webtransport = session.webtransport_sessions.get(owner_stream_id)
            if webtransport is not None:
                await webtransport.feed_stream_data(
                    data,
                    end_stream=fin,
                    disconnect_on_end=False,
                    stream_id=stream_id,
                )
            return True, b''
        if owner_stream_id == stream_id:
            return False, data
        if not self._stream_is_client_initiated_bidi(stream_id):
            if not self._stream_is_client_initiated_unidi(stream_id):
                return False, data
            preface = session.webtransport_stream_prefaces.setdefault(stream_id, bytearray())
            preface.extend(data)
            try:
                signal, offset = decode_quic_varint(bytes(preface), 0)
                owner_candidate, offset = decode_quic_varint(bytes(preface), offset)
            except ValueError:
                if fin:
                    session.webtransport_stream_prefaces.pop(stream_id, None)
                    return False, bytes(preface)
                return True, b''
            if signal != self._WEBTRANSPORT_UNIDI_STREAM_SIGNAL:
                session.webtransport_stream_prefaces.pop(stream_id, None)
                return False, bytes(preface)
            remaining = bytes(preface)[offset:]
            webtransport = session.webtransport_sessions.get(owner_candidate)
            if webtransport is None:
                self.trace_webtransport(
                    'webtransport.stream.orphan',
                    **self._trace_session_fields(session),
                    stream_id=stream_id,
                    owner_stream_id=owner_candidate,
                    stream_direction='client_to_server',
                )
                raise HTTP3ConnectionError(
                    f'invalid WebTransport session id {owner_candidate} on unidirectional stream {stream_id}',
                    error_code=H3_ID_ERROR,
                )
            session.webtransport_streams.add(stream_id)
            session.webtransport_stream_owners[stream_id] = owner_candidate
            session.webtransport_stream_prefaces.pop(stream_id, None)
            self._webtransport_register_stream(webtransport, stream_id)
            self.trace_webtransport(
                'webtransport.stream.dispatch',
                **self._trace_session_fields(session),
                session_id=webtransport.session_id,
                stream_id=stream_id,
                owner_stream_id=owner_candidate,
                owner_session_id=webtransport.session_id,
                stream_direction='client_to_server',
                bytes=len(remaining),
                fin=bool(fin),
            )
            await webtransport.feed_stream_data(
                remaining,
                end_stream=fin,
                disconnect_on_end=False,
                stream_id=stream_id,
                stream_direction='client_to_server',
            )
            return True, b''
        if stream_id in session.h3.requests:
            return False, data

        preface = session.webtransport_stream_prefaces.setdefault(stream_id, bytearray())
        preface.extend(data)
        parsed = self._parse_webtransport_bidi_stream_prefix(bytes(preface))
        if parsed is None:
            if fin:
                payload = bytes(preface)
                session.webtransport_stream_prefaces.pop(stream_id, None)
                return False, payload
            return True, b''

        signal, owner_candidate, remaining = parsed
        if signal != self._WEBTRANSPORT_BIDI_STREAM_SIGNAL:
            session.webtransport_stream_prefaces.pop(stream_id, None)
            return False, bytes(preface)

        webtransport = session.webtransport_sessions.get(owner_candidate)
        if webtransport is None:
            self.trace_webtransport(
                'webtransport.stream.orphan',
                **self._trace_session_fields(session),
                stream_id=stream_id,
                owner_stream_id=owner_candidate,
            )
            raise HTTP3ConnectionError(
                f'invalid WebTransport session id {owner_candidate} on stream {stream_id}',
                error_code=H3_ID_ERROR,
            )
        session.webtransport_streams.add(stream_id)
        session.webtransport_stream_owners[stream_id] = owner_candidate
        session.webtransport_stream_prefaces.pop(stream_id, None)
        self._webtransport_register_stream(webtransport, stream_id)
        self.trace_webtransport(
            'webtransport.stream.dispatch',
            **self._trace_session_fields(session),
            session_id=webtransport.session_id,
            stream_id=stream_id,
            owner_stream_id=owner_candidate,
            owner_session_id=webtransport.session_id,
            stream_direction='bidi',
            bytes=len(remaining),
            fin=bool(fin),
        )
        await webtransport.feed_stream_data(
            remaining,
            end_stream=fin,
            disconnect_on_end=False,
            stream_id=stream_id,
        )
        return True, b''
    async def _send_webtransport_stream_data(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        end_stream: bool,
        endpoint: UDPEndpoint,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._send_webtransport_stream_data(
                    session,
                    stream_id,
                    data,
                    end_stream=end_stream,
                    endpoint=endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        owner_stream_id = session.webtransport_stream_owners.get(stream_id)
        if owner_stream_id is None:
            self.trace_webtransport(
                'webtransport.stream.send.drop',
                **self._trace_session_fields(session),
                stream_id=stream_id,
                reason='missing-owner',
            )
            return
        self.trace_webtransport(
            'webtransport.stream.send',
            **self._trace_session_fields(session),
            session_id=session.webtransport_sessions.get(owner_stream_id).session_id if owner_stream_id in session.webtransport_sessions else None,
            stream_id=stream_id,
            owner_stream_id=owner_stream_id,
            bytes=len(data),
            fin=bool(end_stream),
        )
        if owner_stream_id == stream_id:
            outbound = self._build_http3_data_datagrams_locked(session, stream_id, data, end_stream=end_stream)
        else:
            wire_data = data
            if (
                self._stream_is_server_initiated_bidi(stream_id)
                and stream_id not in session.webtransport_server_prefaced_streams
            ):
                wire_data = (
                    encode_quic_varint(self._WEBTRANSPORT_BIDI_STREAM_SIGNAL)
                    + encode_quic_varint(owner_stream_id)
                    + wire_data
                )
                session.webtransport_server_prefaced_streams.add(stream_id)
            outbound = [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, wire_data, fin=end_stream)]
        if end_stream:
            session.webtransport_streams.discard(stream_id)
            session.webtransport_stream_owners.pop(stream_id, None)
            session.webtransport_stream_prefaces.pop(stream_id, None)
            session.webtransport_server_prefaced_streams.discard(stream_id)
            if owner_stream_id == stream_id:
                webtransport = session.webtransport_sessions.pop(stream_id, None)
                if webtransport is not None:
                    if self.connection_inventory is not None:
                        self.connection_inventory.close_session(webtransport.session_id, reason='stream-closed')
                    self._webtransport_release_session(webtransport.session_id, reason='stream-closed')
                self._release_stream_work_lease(session, stream_id)
            session.h3.abandon_stream(stream_id)
        self._queue_session_outbound_locked(session, outbound, endpoint)
    async def _start_webtransport_stream_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        header_map: dict[bytes, bytes],
        endpoint: UDPEndpoint,
    ) -> list[bytes]:
        negotiation = session.webtransport_negotiation
        if negotiation is None or negotiation.selected_profile is None:
            raise ProtocolError('WebTransport profile is not selected')
        profile = profile_spec(
            negotiation.selected_profile,
            max_sessions=int(self.config.webtransport.max_sessions or 1),
        )
        request = self._build_request(request_state, header_map)
        authority = header_map.get(b':authority')
        if self.config.allowed_server_names and not authority_allowed(authority, self.config.allowed_server_names):
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 421, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                421,
                [(b'content-type', b'text/plain')],
                b'misdirected request',
                end_stream=True,
            )
        if not self._admit_stream_work(session, stream_id):
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 503, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                503,
                [(b'content-type', b'text/plain')],
                b'scheduler overloaded',
                end_stream=True,
            )
        response_headers: list[tuple[bytes, bytes]] = list(profile.response_headers)
        draft = next((value for name, value in request_state.headers if name.lower() == b'sec-webtransport-http3-draft'), None)
        if draft and not response_headers:
            response_headers.append((b'sec-webtransport-http3-draft', draft))
        session.webtransport_streams.add(stream_id)
        session.webtransport_stream_owners[stream_id] = stream_id
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        webtransport = _HTTP3WebTransportSession(
            handler=self,
            session=session,
            stream_id=stream_id,
            request=request,
            client=session.addr,
            server=server,
            scheme='https' if self.listener.scheme in {'https', 'wss'} else self.listener.scheme,
            endpoint=endpoint,
            work_lease=session.stream_work_leases.get(stream_id),
        )
        session.webtransport_sessions[stream_id] = webtransport
        if self.connection_inventory is not None:
            self.connection_inventory.open_session(
                webtransport.session_id,
                connection_id=self._connection_id_for_session(session),
                kind='webtransport',
                stream_ids=(str(stream_id),),
                metadata={
                    'path': request.path,
                    'protocol': 'http3',
                    'carrier': 'h3',
                    'webtransport_profile': profile.profile.value,
                    'webtransport_setting': f'{profile.setting_codepoint:#x}',
                },
            )
        try:
            self._webtransport_register_session(session, webtransport)
            self._webtransport_register_stream(webtransport, stream_id)
        except WebTransportGovernanceError:
            if self.connection_inventory is not None:
                self.connection_inventory.close_session(webtransport.session_id, reason='webtransport-governance-rejected')
            session.webtransport_sessions.pop(stream_id, None)
            session.webtransport_streams.discard(stream_id)
            session.webtransport_stream_owners.pop(stream_id, None)
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 429, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                429,
                [(b'content-type', b'text/plain')],
                b'webtransport resource budget exceeded',
                end_stream=True,
            )
        self.trace_webtransport(
            'webtransport.connect.start',
            **self._trace_session_fields(session),
            session_id=webtransport.session_id,
            stream_id=stream_id,
            path=request.path,
            profile=profile.profile.value,
            setting_id=f'{profile.setting_codepoint:#x}',
        )
        await webtransport.start()
        self.access_logger.log_http(session.addr, 'CONNECT', request.path, 200, 'HTTP/3')
        self.trace_webtransport(
            'webtransport.connect.response',
            **self._trace_session_fields(session),
            session_id=webtransport.session_id,
            stream_id=stream_id,
            status=200,
            end_stream=False,
        )
        return self._build_http3_response_datagrams_locked(session, stream_id, 200, response_headers, b'', end_stream=False)
    async def _drain_webtransport_request_body_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
    ) -> None:
        webtransport = session.webtransport_sessions.get(stream_id)
        if webtransport is None:
            return
        chunk_count = len(request_state.body_parts)
        byte_count = sum(len(chunk) for chunk in request_state.body_parts)
        request_state.body_parts.clear()
        if chunk_count:
            self.trace_webtransport(
                'webtransport.connect.body.drop',
                **self._trace_session_fields(session),
                session_id=webtransport.session_id,
                stream_id=stream_id,
                chunks=chunk_count,
                bytes=byte_count,
            )
        if request_state.ended:
            webtransport.note_connect_stream_stopped()
