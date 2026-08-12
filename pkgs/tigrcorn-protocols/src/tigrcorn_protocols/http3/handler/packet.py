from __future__ import annotations
from .imports import *

logger = logging.getLogger("tigrcorn")

class HTTP3PacketMixin:
    async def handle_packet(self, packet: UDPPacket, endpoint: UDPEndpoint) -> None:
        # Route established traffic directly to its connection lock. Sending
        # every media packet through the global registry creates an event-loop
        # convoy even when the lock itself is held only briefly.
        known_session = None
        try:
            routing_packet = decode_packet(
                packet.data,
                destination_connection_id_length=8,
            )
        except Exception:
            routing_packet = None
        if isinstance(routing_packet, QuicLongHeaderPacket):
            routing_dcid = routing_packet.destination_connection_id
            routing_fresh_initial = (
                routing_packet.packet_type == QuicLongHeaderType.INITIAL
                and not routing_packet.token
            )
            known_session = self.sessions_by_local_cid.get(routing_dcid)
            if known_session is None and not routing_fresh_initial:
                known_session = self.sessions.get(packet.addr)
        elif isinstance(routing_packet, QuicShortHeaderPacket):
            known_session = self.sessions_by_local_cid.get(
                routing_packet.destination_connection_id
            ) or self.sessions.get(packet.addr)

        # QUIC long-header packets carry Initial/Handshake traffic. Admit that
        # work ahead of established short-header media so a busy presentation
        # cannot consume Chromium's four-second connection-opening budget.
        is_long_header = bool(packet.data and packet.data[0] & 0x80)
        if known_session is not None:
            lock_context = (
                known_session.lock.urgent()
                if is_long_header
                else known_session.lock.normal()
            )
        else:
            lock_context = (
                self._lock.urgent()
                if is_long_header
                else self._lock.normal()
            )
        async with lock_context as packet_lock:
            try:
                parsed = decode_packet(packet.data, destination_connection_id_length=8)
            except Exception as exc:
                self.trace_webtransport(
                    'quic.packet.decode_error',
                    addr=f'{packet.addr[0]}:{packet.addr[1]}',
                    bytes=len(packet.data),
                    error=type(exc).__name__,
                    message=str(exc),
                )
                return
            if isinstance(parsed, QuicVersionNegotiationPacket):
                return
            if isinstance(parsed, QuicLongHeaderPacket):
                dcid = parsed.destination_connection_id
                scid = parsed.source_connection_id
            elif isinstance(parsed, QuicShortHeaderPacket):
                dcid = parsed.destination_connection_id
                scid = b''
            elif isinstance(parsed, QuicRetryPacket):
                dcid = parsed.destination_connection_id
                scid = parsed.source_connection_id
            else:
                return
            packet_type = (
                parsed.packet_type.name.lower()
                if isinstance(parsed, QuicLongHeaderPacket)
                else type(parsed).__name__
            )
            self.trace_webtransport(
                'quic.packet.receive',
                addr=f'{packet.addr[0]}:{packet.addr[1]}',
                dcid=dcid.hex(),
                scid=scid.hex(),
                packet_type=packet_type,
                bytes=len(packet.data),
            )
            fresh_initial = (
                isinstance(parsed, QuicLongHeaderPacket)
                and parsed.packet_type == QuicLongHeaderType.INITIAL
                and not parsed.token
            )
            if fresh_initial:
                logger.info(
                    "QUIC fresh Initial dequeued addr=%s:%s ingress_queue_ms=%.1f",
                    packet.addr[0],
                    packet.addr[1],
                    (time.monotonic() - packet.received_at) * 1000,
                )
            session = self.sessions_by_local_cid.get(dcid)
            allow_addr_fallback = not fresh_initial
            if session is None and allow_addr_fallback:
                session = self.sessions.get(packet.addr)
            if session is None and isinstance(parsed, QuicShortHeaderPacket):
                for known_cid, known_session in self.sessions_by_local_cid.items():
                    try:
                        candidate = decode_packet(packet.data, destination_connection_id_length=len(known_cid))
                    except Exception:
                        continue
                    if isinstance(candidate, QuicShortHeaderPacket) and candidate.destination_connection_id == known_cid:
                        parsed = candidate
                        dcid = candidate.destination_connection_id
                        session = known_session
                        break
            if known_session is not None and session is None:
                # The routed session closed while this packet waited for its
                # connection lock. It must not be recreated without returning
                # through the registry path.
                return
            predecoded_events = None
            if session is None:
                if 'http3' in self.listener.enabled_protocols:
                    if not isinstance(parsed, QuicLongHeaderPacket) or parsed.packet_type != QuicLongHeaderType.INITIAL:
                        return
                    session = HTTP3Session(
                        addr=packet.addr,
                        quic=QuicConnection(
                            is_client=False,
                            secret=self.listener.quic_secret,
                            local_cid=dcid or b'tigrcorn',
                            remote_cid=scid,
                            require_retry=self.listener.quic_require_retry,
                            max_datagram_size=self.listener.max_datagram_size,
                        ),
                    )
                    self._assign_session_runtime_id(session)
                    self._configure_session_handshake(session)
                    self.trace_webtransport(
                        'quic.session.create',
                        **self._trace_session_fields(session),
                        dcid=dcid.hex(),
                        scid=scid.hex(),
                    )
                else:
                    candidate_session = None
                    for cid_length in range(1, 21):
                        try:
                            candidate_packet = decode_packet(packet.data, destination_connection_id_length=cid_length)
                        except Exception:
                            continue
                        if not isinstance(candidate_packet, QuicShortHeaderPacket):
                            continue
                        probe = HTTP3Session(
                            addr=packet.addr,
                            quic=QuicConnection(
                                is_client=False,
                                secret=self.listener.quic_secret,
                                local_cid=candidate_packet.destination_connection_id,
                                remote_cid=candidate_packet.destination_connection_id,
                                require_retry=self.listener.quic_require_retry,
                                max_datagram_size=self.listener.max_datagram_size,
                            ),
                        )
                        self._assign_session_runtime_id(probe)
                        try:
                            events = probe.quic.receive_datagram(packet.data, addr=packet.addr)
                        except Exception:
                            continue
                        if any(event.kind != 'integrity_error' for event in events):
                            candidate_session = probe
                            parsed = candidate_packet
                            predecoded_events = events
                            break
                    if candidate_session is None:
                        return
                    session = candidate_session
                    self._assign_session_runtime_id(session)
                    self._configure_session_handshake(session)
                self.sessions[packet.addr] = session
                if session.quic.local_cid:
                    self.sessions_by_local_cid[session.quic.local_cid] = session
                self._register_h3_connection(session)
                if self.metrics is not None:
                    self.metrics.quic_session_opened()
            else:
                session.quic.remote_cid = scid or session.quic.remote_cid
            # Session discovery and registration require only the short global
            # critical section above. All QUIC/H3 state after this point is
            # connection-local, so media backpressure on one connection must
            # not consume another connection's handshake budget.
            await packet_lock.handoff(
                session.lock,
                urgent=isinstance(parsed, QuicLongHeaderPacket),
            )
            outbound: list[bytes] = []
            session.last_activity_at = time.monotonic()
            session.bytes_received += len(packet.data)
            if self.metrics is not None:
                self.metrics.quic_datagram_received(len(packet.data))
            if predecoded_events is None:
                try:
                    events = session.quic.receive_datagram(packet.data, addr=packet.addr)
                except Exception:
                    return
            else:
                events = predecoded_events
            if session.addr != packet.addr and not any(event.kind == 'close' for event in events):
                self.sessions.pop(session.addr, None)
                session.addr = packet.addr
                session.address_validated = True
                session.quic.address_validated = True
                self.sessions[packet.addr] = session
                self._webtransport_register_rebinding(session)
                self._update_h3_connection(session)
            if session.quic.local_cid:
                self.sessions_by_local_cid[session.quic.local_cid] = session
            if session.quic.retry_source_connection_id:
                self.sessions_by_local_cid[session.quic.retry_source_connection_id] = session
            session.request_packets += 1
            outbound.extend(self._ensure_server_control_stream_locked(session))
            for event in events:
                self.trace_webtransport(
                    'quic.event',
                    **self._trace_session_fields(session),
                    kind=event.kind,
                    stream_id=event.stream_id,
                )
                if self.metrics is not None:
                    if event.kind == 'retry':
                        self.metrics.quic_retry_emitted()
                    elif event.kind == 'path_challenge':
                        self.metrics.quic_path_challenge_observed()
                    elif event.kind == 'path_response':
                        self.metrics.quic_path_response_observed()
                    elif event.kind == 'path_migrated':
                        self.metrics.quic_path_migrated()
                    elif event.kind == 'reset_stream':
                        self.metrics.http3_stream_reset()
                if event.kind == 'handshake_complete':
                    self.trace_webtransport('quic.handshake.complete', **self._trace_session_fields(session))
                    session.address_validated = True
                    session.quic.address_validated = True
                    if self.metrics is not None:
                        self.metrics.tls_handshake_completed()
                        if not session.early_data_accounted and session.quic.handshake_driver is not None:
                            using_psk = bool(getattr(session.quic.handshake_driver, '_using_psk', False))
                            if using_psk:
                                accepted = bool(getattr(session.quic.handshake_driver, 'early_data_accepted', False))
                                self.metrics.quic_early_data_observed(accepted=accepted)
                                session.early_data_accounted = True
                    outbound.extend(session.quic.take_handshake_datagrams())
                    outbound.extend(self._ensure_server_control_stream_locked(session))
                    if (
                        session.quic.handshake_driver is not None
                        and not session.quic.is_client
                        and not session.session_ticket_issued
                    ):
                        try:
                            ticket = session.quic.handshake_driver.issue_session_ticket(
                                max_early_data_size=self._session_ticket_early_data_size(session)
                            )
                        except Exception:
                            ticket = b''
                        if ticket:
                            outbound.append(session.quic.send_crypto_data(ticket, packet_space='application'))
                            session.session_ticket_issued = True
                elif event.kind == 'path_response':
                    session.address_validated = True
                    session.quic.address_validated = True
                    outbound.extend(self._ensure_server_control_stream_locked(session))
                elif event.kind == 'stream' and event.stream_id is not None:
                    self.trace_webtransport(
                        'quic.stream.receive',
                        **self._trace_session_fields(session),
                        stream_id=event.stream_id,
                        bytes=len(event.data),
                        fin=bool(event.fin),
                    )
                    if 'http3' in self.listener.enabled_protocols:
                        try:
                            handled, h3_payload = await self._consume_webtransport_stream_event_locked(
                                session,
                                event.stream_id,
                                event.data,
                                fin=event.fin,
                            )
                        except HTTP3ConnectionError as exc:
                            outbound.extend(self._flush_qpack_streams(session))
                            outbound.append(session.quic.close(error_code=exc.error_code, reason=str(exc), application=True))
                            await self._abort_session_tunnels(session)
                            await self._abort_session_websockets(session)
                            await self._abort_session_webtransports(session)
                            self._cancel_session_timer(session)
                            self._close_session(session)
                            break
                        if handled:
                            continue
                        try:
                            peer_goaway_before = session.h3.state.peer_goaway_id
                            request_state = session.h3.receive_stream_data(event.stream_id, h3_payload, fin=event.fin)
                            if (
                                self.metrics is not None
                                and session.h3.state.peer_goaway_id is not None
                                and session.h3.state.peer_goaway_id != peer_goaway_before
                            ):
                                self.metrics.http3_goaway_observed()
                        except HTTP3StreamError as exc:
                            if exc.stream_id is not None:
                                session.h3.abandon_stream(exc.stream_id)
                            outbound.extend(self._flush_qpack_streams(session))
                            if exc.stream_id is not None:
                                outbound.append(session.quic.reset_stream(exc.stream_id, exc.error_code))
                            continue
                        except HTTP3ConnectionError as exc:
                            outbound.extend(self._flush_qpack_streams(session))
                            outbound.append(session.quic.close(error_code=exc.error_code, reason=str(exc), application=True))
                            await self._abort_session_tunnels(session)
                            await self._abort_session_websockets(session)
                            await self._abort_session_webtransports(session)
                            self._cancel_session_timer(session)
                            self._close_session(session)
                            break
                        except ProtocolError as exc:
                            outbound.extend(self._flush_qpack_streams(session))
                            outbound.append(session.quic.close(error_code=H3_GENERAL_PROTOCOL_ERROR, reason=str(exc), application=True))
                            await self._abort_session_tunnels(session)
                            await self._abort_session_websockets(session)
                            await self._abort_session_webtransports(session)
                            self._cancel_session_timer(session)
                            self._close_session(session)
                            break
                        outbound.extend(self._flush_qpack_streams(session))
                        if request_state is not None:
                            header_map: dict[bytes, bytes] | None = None
                            if request_state.received_initial_headers:
                                try:
                                    header_map = self._validate_request_headers(list(request_state.headers))
                                except ProtocolError:
                                    if event.stream_id not in session.responded_streams:
                                        outbound.extend(
                                            self._build_http3_response_datagrams_locked(
                                                session,
                                                event.stream_id,
                                                400,
                                                [(b'content-type', b'text/plain')],
                                                b'bad request',
                                                end_stream=True,
                                            )
                                        )
                                        session.responded_streams.add(event.stream_id)
                                    outbound.extend(await self._respond_ready_requests(session, endpoint))
                                    continue
                            protocol = header_map.get(b':protocol') if header_map is not None else None
                            if header_map is not None and protocol is not None and event.stream_id not in session.responded_streams:
                                if (
                                    'webtransport' in self.listener.enabled_protocols
                                    and self._is_configured_webtransport_token(protocol)
                                ):
                                    outbound.extend(await self._admit_webtransport_connect(
                                        session, event.stream_id, request_state, header_map, endpoint
                                    ))
                                elif protocol != b'websocket' or not self.listener.websocket:
                                    target = self._request_target_from_header_map(header_map)
                                    self.access_logger.log_http(session.addr, 'CONNECT', target, 501, 'HTTP/3')
                                    outbound.extend(
                                        self._build_http3_response_datagrams_locked(
                                            session,
                                            event.stream_id,
                                            501,
                                            [(b'content-type', b'text/plain')],
                                            b'unsupported extended connect protocol',
                                            end_stream=True,
                                        )
                                    )
                                else:
                                    outbound.extend(
                                        await self._start_websocket_stream_locked(
                                            session,
                                            event.stream_id,
                                            request_state,
                                            header_map,
                                            endpoint,
                                        )
                                    )
                                session.responded_streams.add(event.stream_id)
                            elif header_map is not None and header_map.get(b':method') == b'CONNECT' and event.stream_id not in session.responded_streams:
                                outbound.extend(
                                    await self._start_connect_tunnel_locked(
                                        session,
                                        event.stream_id,
                                        request_state,
                                        header_map,
                                        endpoint,
                                    )
                                )
                                session.responded_streams.add(event.stream_id)
                            if event.stream_id in session.websocket_sessions:
                                await self._drain_websocket_request_body_locked(session, event.stream_id, request_state, endpoint)
                            elif event.stream_id in session.connect_tunnels:
                                await self._drain_connect_request_body_locked(session, event.stream_id, request_state)
                            elif event.stream_id in session.webtransport_streams:
                                await self._drain_webtransport_request_body_locked(session, event.stream_id, request_state)
                            elif request_state.ready and event.stream_id not in session.responded_streams:
                                outbound.extend(await self._invoke_http_app(session, event.stream_id, request_state, endpoint))
                                session.responded_streams.add(event.stream_id)
                        outbound.extend(await self._respond_ready_requests(session, endpoint))
                    else:
                        outbound.extend(await self._invoke_custom_quic_app(session, event, endpoint))
                        if event.stream_id is not None:
                            session.responded_streams.add(event.stream_id)
                elif event.kind == 'reset_stream' and event.stream_id is not None:
                    if 'http3' in self.listener.enabled_protocols:
                        websocket = session.websocket_sessions.get(event.stream_id)
                        if websocket is not None:
                            await websocket.abort()
                            session.websocket_sessions.pop(event.stream_id, None)
                        tunnel = session.connect_tunnels.get(event.stream_id)
                        if tunnel is not None:
                            await tunnel.abort()
                        if event.stream_id in session.webtransport_streams:
                            owner_stream_id = session.webtransport_stream_owners.get(event.stream_id, event.stream_id)
                            webtransport = session.webtransport_sessions.get(owner_stream_id)
                            if owner_stream_id == event.stream_id and webtransport is not None:
                                webtransport.note_connect_stream_stopped()
                            else:
                                session.webtransport_streams.discard(event.stream_id)
                                session.webtransport_stream_prefaces.pop(event.stream_id, None)
                                session.webtransport_stream_owners.pop(event.stream_id, None)
                                if webtransport is not None:
                                    self._webtransport_release_stream(
                                        webtransport, event.stream_id
                                    )
                                webtransport = session.webtransport_sessions.pop(owner_stream_id, None) if owner_stream_id == event.stream_id else None
                                if webtransport is not None:
                                    await webtransport.abort()
                                    self._release_stream_work_lease(session, event.stream_id)
                        if event.stream_id not in session.webtransport_sessions:
                            session.h3.abandon_stream(event.stream_id)
                        outbound.extend(self._flush_qpack_streams(session))
                elif event.kind == 'stop_sending' and event.stream_id is not None:
                    if 'http3' in self.listener.enabled_protocols and event.stream_id in session.webtransport_sessions:
                        session.quic.suppress_pending_reset(event.stream_id)
                        webtransport = session.webtransport_sessions.get(event.stream_id)
                        if webtransport is not None:
                            webtransport.note_connect_stream_stopped()
                elif event.kind == 'datagram':
                    if 'http3' in self.listener.enabled_protocols:
                        self.trace_webtransport(
                            'quic.datagram.receive',
                            **self._trace_session_fields(session),
                            bytes=len(event.data),
                        )
                        await self._dispatch_webtransport_datagram_locked(session, event.data)
                elif event.kind == 'close':
                    close_reason = getattr(event.detail, 'reason', '')
                    close_code = getattr(event.detail, 'error_code', None)
                    self.trace_webtransport(
                        'quic.connection.close.receive',
                        **self._trace_session_fields(session),
                        error_code=close_code,
                        reason=close_reason,
                    )
                    logger.warning(
                        "QUIC connection closing code=%s reason=%s",
                        close_code,
                        close_reason or "peer did not provide a reason",
                    )
                    await self._abort_session_tunnels(session)
                    await self._abort_session_websockets(session)
                    await self._abort_session_webtransports(session)
                    self._cancel_session_timer(session)
                    self._close_session(session)
            self._sync_quic_loss_metrics(session)
            self._update_h3_connection(session)
            outbound.extend(session.quic.take_handshake_datagrams())
            outbound.extend(session.quic.drain_scheduled_datagrams())
            # This path carries transport ACK/flow-control plus request
            # responses. Keep it ahead of bulk application media so ACKs can
            # continuously release congestion credit.
            self._queue_session_outbound_locked(
                session, outbound, endpoint, priority=True
            )
            if fresh_initial:
                logger.info(
                    "QUIC fresh Initial response queued addr=%s:%s total_ms=%.1f datagrams=%d",
                    packet.addr[0],
                    packet.addr[1],
                    (time.monotonic() - packet.received_at) * 1000,
                    len(outbound),
                )
