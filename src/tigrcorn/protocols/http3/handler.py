from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from tigrcorn.asgi.receive import HTTPRequestReceive, apply_request_trailer_policy
from tigrcorn.asgi.scopes.custom import build_custom_scope
from tigrcorn.asgi.scopes.http import build_http_scope
from tigrcorn.asgi.send import HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger
from tigrcorn.observability.metrics import Metrics
from tigrcorn.security.tls import build_server_ssl_context
from tigrcorn.protocols.connect import close_tcp_writer, half_close_tcp_writer, is_connect_allowed, parse_connect_authority
from tigrcorn.protocols.custom.adapters import adapt_scope
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.http.alt_svc import configured_alt_svc_values
from tigrcorn.http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn.protocols.http3.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    H3_CONNECT_ERROR,
    H3_GENERAL_PROTOCOL_ERROR,
    H3_REQUEST_CANCELLED,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    HTTP3ConnectionError,
    HTTP3StreamError,
    encode_frame,
)
from tigrcorn.protocols.http3.streams import (
    STREAM_TYPE_QPACK_DECODER,
    STREAM_TYPE_QPACK_ENCODER,
    HTTP3ConnectionCore,
)
from tigrcorn.protocols.http3.websocket import H3WebSocketSession
from tigrcorn.transports.quic.connection import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters
from tigrcorn.transports.quic.packets import QuicLongHeaderPacket, QuicLongHeaderType, QuicRetryPacket, QuicShortHeaderPacket, QuicVersionNegotiationPacket, decode_packet
from tigrcorn.transports.udp.endpoint import UDPEndpoint
from tigrcorn.transports.udp.packet import UDPPacket
from tigrcorn.types import ASGIApp
from tigrcorn.utils.bytes import encode_quic_varint
from tigrcorn.utils.authority import authority_allowed
from tigrcorn.utils.headers import apply_response_header_policy, sanitize_early_hints_headers, strip_connection_specific_headers


@dataclass(slots=True)
class HTTP3Session:
    addr: tuple[str, int]
    quic: QuicConnection
    h3: HTTP3ConnectionCore = field(default_factory=lambda: HTTP3ConnectionCore(role='server'))
    server_control_stream_sent: bool = False
    server_control_stream_id: int | None = None
    responded_streams: set[int] = field(default_factory=set)
    request_packets: int = 0
    server_qpack_encoder_stream_id: int | None = None
    server_qpack_decoder_stream_id: int | None = None
    bytes_received: int = 0
    bytes_sent: int = 0
    address_validated: bool = False
    session_ticket_issued: bool = False
    pending_outbound: list[bytes] = field(default_factory=list)
    timer_handle: asyncio.TimerHandle | None = None
    connect_tunnels: dict[int, _HTTP3ConnectTunnel] = field(default_factory=dict)
    websocket_sessions: dict[int, H3WebSocketSession] = field(default_factory=dict)
    stream_work_leases: dict[int, object] = field(default_factory=dict)


class _HTTP3ConnectTunnel:
    def __init__(
        self,
        *,
        handler: HTTP3DatagramHandler,
        session: HTTP3Session,
        stream_id: int,
        authority: str,
        endpoint: UDPEndpoint,
        upstream_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
        work_lease: object | None = None,
    ) -> None:
        self.handler = handler
        self.session = session
        self.stream_id = stream_id
        self.authority = authority
        self.endpoint = endpoint
        self.upstream_reader = upstream_reader
        self.upstream_writer = upstream_writer
        self.work_lease = work_lease
        self.relay_task: asyncio.Task[None] | None = None
        self.client_input_closed = False
        self.server_output_closed = False
        self.closed = False

    def start(self) -> None:
        self.relay_task = asyncio.create_task(
            self._relay_upstream_to_client(),
            name=f'tigrcorn-h3-connect-{self.stream_id}',
        )

    async def feed_client_data(self, chunks: list[bytes], *, end_stream: bool, already_locked: bool = False) -> None:
        if self.closed:
            return
        try:
            wrote = False
            for chunk in chunks:
                if not chunk:
                    continue
                self.upstream_writer.write(chunk)
                wrote = True
            if wrote:
                await self.upstream_writer.drain()
            if end_stream and not self.client_input_closed:
                self.client_input_closed = True
                await half_close_tcp_writer(self.upstream_writer)
        except Exception:
            await self.handler._reset_http3_tunnel_stream(
                self.session,
                self.stream_id,
                self.endpoint,
                already_locked=already_locked,
            )
            await self.abort()
            return
        await self._finish_if_complete()

    async def abort(self) -> None:
        if self.closed:
            return
        self.closed = True
        current = asyncio.current_task()
        if self.relay_task is not None and self.relay_task is not current:
            self.relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.relay_task
        self.session.connect_tunnels.pop(self.stream_id, None)
        lease = self.session.stream_work_leases.pop(self.stream_id, None)
        if lease is not None:
            lease.release()
        elif self.work_lease is not None:
            self.work_lease.release()
        await close_tcp_writer(self.upstream_writer)

    async def _relay_upstream_to_client(self) -> None:
        reset_stream = False
        try:
            while True:
                chunk = await asyncio.wait_for(self.upstream_reader.read(65536), timeout=self.handler.config.http.idle_timeout)
                if not chunk:
                    break
                await self.handler._send_http3_tunnel_data(
                    self.session,
                    self.stream_id,
                    chunk,
                    end_stream=False,
                    endpoint=self.endpoint,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            reset_stream = True
        else:
            with suppress(Exception):
                await self.handler._send_http3_tunnel_data(
                    self.session,
                    self.stream_id,
                    b'',
                    end_stream=True,
                    endpoint=self.endpoint,
                )
        finally:
            self.server_output_closed = True
            if reset_stream:
                with suppress(Exception):
                    await self.handler._reset_http3_tunnel_stream(self.session, self.stream_id, self.endpoint)
            await self._finish_if_complete()

    async def _finish_if_complete(self) -> None:
        if self.client_input_closed and self.server_output_closed:
            await self.abort()


class HTTP3DatagramHandler:
    _EARLY_DATA_TICKET_SIZE = 4096

    def __init__(self, *, app: ASGIApp, config: ServerConfig, listener: ListenerConfig, access_logger: AccessLogger, scheduler: ProductionScheduler | None = None, metrics: Metrics | None = None) -> None:
        self.app = app
        self.config = config
        self.listener = listener
        self.access_logger = access_logger
        self.scheduler = scheduler
        self.metrics = metrics
        self.sessions: dict[tuple[str, int], HTTP3Session] = {}
        self.sessions_by_local_cid: dict[bytes, HTTP3Session] = {}
        self._lock = asyncio.Lock()

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
        transport_parameters = TransportParameters(max_udp_payload_size=self.listener.max_datagram_size, max_streams_bidi=self.config.scheduler.max_streams or 128, max_streams_uni=self.config.scheduler.max_streams or 128, idle_timeout=int(self.config.quic.idle_timeout * 1000))
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

    def _queue_or_send(self, session: HTTP3Session, raw: bytes, endpoint: UDPEndpoint, addr: tuple[str, int]) -> None:
        transport = getattr(endpoint, 'transport', None)
        if transport is not None and transport.is_closing():
            return
        if self._can_send_now(session, raw):
            endpoint.send(raw, addr)
            session.bytes_sent += len(raw)
            return
        session.quic.defer_datagram(raw)
        session.pending_outbound.append(raw)

    def _flush_pending_outbound(self, session: HTTP3Session, endpoint: UDPEndpoint) -> None:
        if not session.pending_outbound:
            return
        transport = getattr(endpoint, 'transport', None)
        if transport is not None and transport.is_closing():
            return
        remaining: list[bytes] = []
        for raw in session.pending_outbound:
            if self._can_send_now(session, raw):
                session.quic.confirm_datagram_sent(raw)
                endpoint.send(raw, session.addr)
                session.bytes_sent += len(raw)
            else:
                remaining.append(raw)
        session.pending_outbound = remaining

    def _can_send_now(self, session: HTTP3Session, raw: bytes) -> bool:
        amplification_ok = session.address_validated or (session.bytes_sent + len(raw) <= (session.bytes_received * 3))
        return amplification_ok and session.quic.can_transmit_datagram(raw)

    def _cancel_session_timer(self, session: HTTP3Session) -> None:
        if session.timer_handle is not None:
            session.timer_handle.cancel()
            session.timer_handle = None

    def _next_session_delay(self, session: HTTP3Session) -> float | None:
        delays: list[float] = []
        runtime_delay = session.quic.next_runtime_deadline()
        if runtime_delay is not None:
            delays.append(runtime_delay)
        for raw in session.pending_outbound:
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
            outbound = session.quic.drain_scheduled_datagrams()
            for raw in outbound:
                self._queue_or_send(session, raw, endpoint, session.addr)
            self._flush_pending_outbound(session, endpoint)
            self._arm_session_timer(session, endpoint)

    async def handle_packet(self, packet: UDPPacket, endpoint: UDPEndpoint) -> None:
        async with self._lock:
            try:
                parsed = decode_packet(packet.data, destination_connection_id_length=8)
            except Exception:
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
            session = self.sessions_by_local_cid.get(dcid)
            allow_addr_fallback = not (
                isinstance(parsed, QuicLongHeaderPacket)
                and parsed.packet_type == QuicLongHeaderType.INITIAL
                and not parsed.token
            )
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
                        ),
                    )
                    self._configure_session_handshake(session)
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
                            ),
                        )
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
                    self._configure_session_handshake(session)
                self.sessions[packet.addr] = session
                if session.quic.local_cid:
                    self.sessions_by_local_cid[session.quic.local_cid] = session
            else:
                session.quic.remote_cid = scid or session.quic.remote_cid

            outbound: list[bytes] = []

            session.bytes_received += len(packet.data)
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
            if session.quic.local_cid:
                self.sessions_by_local_cid[session.quic.local_cid] = session
            session.request_packets += 1
            outbound.extend(self._ensure_server_control_stream_locked(session))
            for event in events:
                if event.kind == 'handshake_complete':
                    session.address_validated = True
                    session.quic.address_validated = True
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
                    if 'http3' in self.listener.enabled_protocols:
                        try:
                            request_state = session.h3.receive_stream_data(event.stream_id, event.data, fin=event.fin)
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
                            self._cancel_session_timer(session)
                            self.sessions.pop(session.addr, None)
                            self.sessions_by_local_cid.pop(session.quic.local_cid, None)
                            break
                        except ProtocolError as exc:
                            outbound.extend(self._flush_qpack_streams(session))
                            outbound.append(session.quic.close(error_code=H3_GENERAL_PROTOCOL_ERROR, reason=str(exc), application=True))
                            await self._abort_session_tunnels(session)
                            await self._abort_session_websockets(session)
                            self._cancel_session_timer(session)
                            self.sessions.pop(session.addr, None)
                            self.sessions_by_local_cid.pop(session.quic.local_cid, None)
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
                                if protocol != b'websocket' or not self.listener.websocket:
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
                        session.h3.abandon_stream(event.stream_id)
                        outbound.extend(self._flush_qpack_streams(session))
                elif event.kind == 'close':
                    await self._abort_session_tunnels(session)
                    await self._abort_session_websockets(session)
                    self._cancel_session_timer(session)
                    self.sessions.pop(session.addr, None)
                    self.sessions_by_local_cid.pop(session.quic.local_cid, None)
            outbound.extend(session.quic.take_handshake_datagrams())
            outbound.extend(session.quic.drain_scheduled_datagrams())
            for raw in outbound:
                self._queue_or_send(session, raw, endpoint, packet.addr)
            self._flush_pending_outbound(session, endpoint)
            if session.addr in self.sessions and self.sessions.get(session.addr) is session:
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
        control_settings = {1: 0, 6: self.listener.max_datagram_size}
        if self.listener.websocket:
            control_settings[SETTING_ENABLE_CONNECT_PROTOCOL] = 1
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
            outbound.append(session.quic.send_stream_data(session.server_qpack_encoder_stream_id, encoder_data, fin=False))
        decoder_data = session.h3.take_decoder_stream_data()
        if decoder_data:
            if session.server_qpack_decoder_stream_id is None:
                session.server_qpack_decoder_stream_id = session.quic.streams.next_stream_id(client=False, unidirectional=True)
                decoder_data = encode_quic_varint(STREAM_TYPE_QPACK_DECODER) + decoder_data
            outbound.append(session.quic.send_stream_data(session.server_qpack_decoder_stream_id, decoder_data, fin=False))
        return outbound

    def _queue_session_outbound_locked(self, session: HTTP3Session, outbound: list[bytes], endpoint: UDPEndpoint) -> None:
        for raw in outbound:
            self._queue_or_send(session, raw, endpoint, session.addr)
        self._flush_pending_outbound(session, endpoint)
        if session.addr in self.sessions and self.sessions.get(session.addr) is session:
            self._arm_session_timer(session, endpoint)

    def _build_http3_response_datagrams_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
        *,
        end_stream: bool,
    ) -> list[bytes]:
        response_headers = apply_response_header_policy(
            strip_connection_specific_headers(headers),
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=configured_alt_svc_values(self.config, request_http_version='3'),
        )
        header_block = session.h3.encode_headers(
            stream_id,
            [(b':status', str(status).encode('ascii')), *response_headers],
        )
        payload = bytearray(encode_frame(FRAME_HEADERS, header_block))
        if body:
            payload.extend(encode_frame(FRAME_DATA, body))
        return [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, bytes(payload), fin=end_stream)]

    async def _send_http3_streamed_response_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body_segments: list,
        trailers: list[tuple[bytes, bytes]],
        informational: list[tuple[int, list[tuple[bytes, bytes]]]],
        endpoint: UDPEndpoint,
    ) -> None:
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        for interim_status, interim_headers in informational:
            interim_header_block = session.h3.encode_headers(
                stream_id,
                [(b':status', str(interim_status).encode('ascii')), *sanitize_early_hints_headers(interim_headers)],
            )
            outbound = [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, encode_frame(FRAME_HEADERS, interim_header_block), fin=False)]
            self._queue_session_outbound_locked(session, outbound, endpoint)
        has_body = response_body_segments_have_bytes(body_segments)
        response_headers = apply_response_header_policy(
            strip_connection_specific_headers(headers),
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
            alt_svc_values=configured_alt_svc_values(self.config, request_http_version='3'),
        )
        header_block = session.h3.encode_headers(stream_id, [(b':status', str(status).encode('ascii')), *response_headers])
        outbound = [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, encode_frame(FRAME_HEADERS, header_block), fin=(not has_body and not trailers))]
        self._queue_session_outbound_locked(session, outbound, endpoint)
        if not has_body and not trailers:
            return
        if has_body:
            chunk_size = max(1024, int(self.listener.max_datagram_size) - 256)
            async for chunk in iter_response_body_segments(body_segments, chunk_size=chunk_size):
                outbound = self._build_http3_data_datagrams_locked(session, stream_id, chunk, end_stream=False)
                self._queue_session_outbound_locked(session, outbound, endpoint)
        if trailers:
            trailer_block = session.h3.encode_headers(stream_id, list(trailers))
            outbound = [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, encode_frame(FRAME_HEADERS, trailer_block), fin=True)]
        else:
            outbound = self._build_http3_data_datagrams_locked(session, stream_id, b'', end_stream=True)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    def _build_http3_data_datagrams_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        data: bytes,
        *,
        end_stream: bool,
    ) -> list[bytes]:
        payload = encode_frame(FRAME_DATA, data) if data else b''
        return [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, payload, fin=end_stream)]

    async def _send_http3_websocket_headers(
        self,
        session: HTTP3Session,
        stream_id: int,
        status: int,
        headers: list[tuple[bytes, bytes]],
        *,
        end_stream: bool,
        endpoint: UDPEndpoint,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._send_http3_websocket_headers(
                    session,
                    stream_id,
                    status,
                    headers,
                    end_stream=end_stream,
                    endpoint=endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        if stream_id not in session.websocket_sessions:
            return
        outbound = self._build_http3_response_datagrams_locked(
            session,
            stream_id,
            status,
            headers,
            b'',
            end_stream=end_stream,
        )
        if end_stream:
            session.websocket_sessions.pop(stream_id, None)
            self._release_stream_work_lease(session, stream_id)
            session.h3.abandon_stream(stream_id)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _send_http3_websocket_data(
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
                await self._send_http3_websocket_data(
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
        if stream_id not in session.websocket_sessions:
            return
        outbound = self._build_http3_data_datagrams_locked(session, stream_id, data, end_stream=end_stream)
        if end_stream:
            session.websocket_sessions.pop(stream_id, None)
            self._release_stream_work_lease(session, stream_id)
            session.h3.abandon_stream(stream_id)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _send_http3_tunnel_data(
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
                await self._send_http3_tunnel_data(
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
        if stream_id not in session.connect_tunnels:
            return
        outbound = self._build_http3_data_datagrams_locked(session, stream_id, data, end_stream=end_stream)
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _reset_http3_tunnel_stream(
        self,
        session: HTTP3Session,
        stream_id: int,
        endpoint: UDPEndpoint,
        *,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._reset_http3_tunnel_stream(
                    session,
                    stream_id,
                    endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)
        outbound = self._flush_qpack_streams(session)
        outbound.append(session.quic.reset_stream(stream_id, H3_CONNECT_ERROR))
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _abort_session_tunnels(self, session: HTTP3Session) -> None:
        for tunnel in list(session.connect_tunnels.values()):
            with suppress(Exception):
                await tunnel.abort()

    async def _reset_http3_websocket_stream(
        self,
        session: HTTP3Session,
        stream_id: int,
        endpoint: UDPEndpoint,
        *,
        already_locked: bool = False,
    ) -> None:
        if not already_locked:
            async with self._lock:
                await self._reset_http3_websocket_stream(
                    session,
                    stream_id,
                    endpoint,
                    already_locked=True,
                )
            return
        if session.addr not in self.sessions or self.sessions.get(session.addr) is not session:
            return
        session.websocket_sessions.pop(stream_id, None)
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)
        outbound = self._flush_qpack_streams(session)
        outbound.append(session.quic.reset_stream(stream_id, H3_REQUEST_CANCELLED))
        self._queue_session_outbound_locked(session, outbound, endpoint)

    async def _abort_session_websockets(self, session: HTTP3Session) -> None:
        for websocket in list(session.websocket_sessions.values()):
            with suppress(Exception):
                await websocket.abort()
        session.websocket_sessions.clear()


    def _release_stream_work_lease(self, session: HTTP3Session, stream_id: int) -> None:
        lease = session.stream_work_leases.pop(stream_id, None)
        if lease is not None:
            lease.release()

    def _on_websocket_stream_closed(self, session: HTTP3Session, stream_id: int) -> None:
        session.websocket_sessions.pop(stream_id, None)
        self._release_stream_work_lease(session, stream_id)
        session.h3.abandon_stream(stream_id)

    def _admit_stream_work(self, session: HTTP3Session, stream_id: int) -> bool:
        if self.scheduler is None:
            return True
        lease = self.scheduler.acquire_work()
        if lease is None:
            if self.metrics is not None:
                self.metrics.scheduler_task_rejected()
            return False
        session.stream_work_leases[stream_id] = lease
        return True

    def _request_target_from_header_map(self, header_map: dict[bytes, bytes]) -> str:
        method = header_map.get(b':method', b'GET')
        if method == b'CONNECT' and header_map.get(b':protocol') is None:
            return header_map.get(b':authority', b'').decode('ascii', 'replace')
        return header_map.get(b':path', b'/').decode('ascii', 'replace')

    def _build_request(self, request_state: Any, header_map: dict[bytes, bytes]) -> ParsedRequest:
        method = header_map.get(b':method', b'GET').decode('ascii', 'replace')
        if method.upper() == 'CONNECT' and header_map.get(b':protocol') is None:
            target = header_map.get(b':authority', b'').decode('ascii', 'replace')
            path = target
            raw_path = target.encode('ascii', 'ignore')
            query = b''
        else:
            target = header_map.get(b':path', b'/').decode('ascii', 'replace')
            raw_path, _, query = target.encode('ascii', 'ignore').partition(b'?')
            path = raw_path.decode('utf-8', 'replace')
        return ParsedRequest(
            method=method,
            target=target,
            path=path,
            raw_path=raw_path,
            query_string=query,
            http_version='3',
            headers=[(k, v) for k, v in request_state.headers if not k.startswith(b':')],
            body=request_state.body,
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=False,
        )

    async def _start_connect_tunnel_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        header_map: dict[bytes, bytes],
        endpoint: UDPEndpoint,
    ) -> list[bytes]:
        authority = header_map.get(b':authority', b'').decode('ascii', 'replace')
        try:
            host, port = parse_connect_authority(authority)
        except Exception:
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 400, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                400,
                [(b'content-type', b'text/plain')],
                b'bad connect target',
                end_stream=True,
            )
        if self.config.http.connect_policy == 'deny':
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 403, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                403,
                [(b'content-type', b'text/plain')],
                b'connect denied',
                end_stream=True,
            )
        if self.config.http.connect_policy == 'allowlist' and not is_connect_allowed(host, port, self.config.http.connect_allow):
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 403, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                403,
                [(b'content-type', b'text/plain')],
                b'connect denied',
                end_stream=True,
            )
        if not self._admit_stream_work(session, stream_id):
            self.access_logger.log_http(session.addr, 'CONNECT', authority or '', 503, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                503,
                [(b'content-type', b'text/plain')],
                b'scheduler overloaded',
                end_stream=True,
            )
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=getattr(self.config, 'read_timeout', 5.0),
            )
        except Exception:
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(session.addr, 'CONNECT', authority, 502, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                502,
                [(b'content-type', b'text/plain')],
                b'bad gateway',
                end_stream=True,
            )
        tunnel = _HTTP3ConnectTunnel(
            handler=self,
            session=session,
            stream_id=stream_id,
            authority=authority,
            endpoint=endpoint,
            upstream_reader=upstream_reader,
            upstream_writer=upstream_writer,
            work_lease=session.stream_work_leases.get(stream_id),
        )
        session.connect_tunnels[stream_id] = tunnel
        tunnel.start()
        self.access_logger.log_http(session.addr, 'CONNECT', authority, 200, 'HTTP/3')
        return self._build_http3_response_datagrams_locked(session, stream_id, 200, [], b'', end_stream=False)

    async def _start_websocket_stream_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        header_map: dict[bytes, bytes],
        endpoint: UDPEndpoint,
    ) -> list[bytes]:
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
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        scheme = header_map.get(
            b':scheme',
            self.listener.scheme.encode('ascii', 'ignore') if self.listener.scheme else b'https',
        ).decode('ascii', 'replace')
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
        try:
            websocket = H3WebSocketSession(
                app=self.app,
                config=self.config,
                request=request,
                client=session.addr,
                server=server,
                scheme=scheme,
                send_headers=lambda status, headers, end_stream: self._send_http3_websocket_headers(
                    session,
                    stream_id,
                    status,
                    headers,
                    end_stream=end_stream,
                    endpoint=endpoint,
                ),
                send_data=lambda data, end_stream: self._send_http3_websocket_data(
                    session,
                    stream_id,
                    data,
                    end_stream=end_stream,
                    endpoint=endpoint,
                ),
                metrics=self.metrics,
                on_close=lambda session=session, stream_id=stream_id: self._on_websocket_stream_closed(session, stream_id),
            )
        except ProtocolError:
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(session.addr, 'CONNECT', request.path, 400, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                400,
                [(b'content-type', b'text/plain')],
                b'bad request',
                end_stream=True,
            )
        session.websocket_sessions[stream_id] = websocket
        await websocket.start()
        return []

    async def _drain_connect_request_body_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
    ) -> None:
        tunnel = session.connect_tunnels.get(stream_id)
        if tunnel is None:
            return
        chunks = list(request_state.body_parts)
        request_state.body_parts.clear()
        await tunnel.feed_client_data(chunks, end_stream=request_state.ended, already_locked=True)

    async def _drain_websocket_request_body_locked(
        self,
        session: HTTP3Session,
        stream_id: int,
        request_state: Any,
        endpoint: UDPEndpoint,
    ) -> None:
        websocket = session.websocket_sessions.get(stream_id)
        if websocket is None:
            return
        chunks = list(request_state.body_parts)
        request_state.body_parts.clear()
        try:
            await websocket.feed_data(b''.join(chunks), end_stream=request_state.ended)
        except Exception:
            await self._reset_http3_websocket_stream(
                session,
                stream_id,
                endpoint,
                already_locked=True,
            )
            await websocket.abort()

    async def _respond_ready_requests(self, session: HTTP3Session, endpoint: UDPEndpoint) -> list[bytes]:
        outbound: list[bytes] = []
        for request_state in session.h3.ready_request_states():
            stream_id = request_state.stream_id
            if not request_state.ended or stream_id in session.responded_streams:
                continue
            outbound.extend(await self._invoke_http_app(session, stream_id, request_state, endpoint))
            session.responded_streams.add(stream_id)
        return outbound

    def _validate_request_headers(self, headers: list[tuple[bytes, bytes]]) -> dict[bytes, bytes]:
        pseudo_seen: set[bytes] = set()
        regular_seen = False
        header_map: dict[bytes, bytes] = {}
        for name, value in headers:
            if any(65 <= byte <= 90 for byte in name):
                raise ProtocolError('uppercase header field name forbidden')
            if name.startswith(b':'):
                if regular_seen:
                    raise ProtocolError('pseudo-header after regular header')
                if name not in {b':method', b':scheme', b':authority', b':path', b':protocol'}:
                    raise ProtocolError('invalid request pseudo-header')
                if name in pseudo_seen:
                    raise ProtocolError('duplicate pseudo-header')
                pseudo_seen.add(name)
            else:
                regular_seen = True
                if name in {b'connection', b'upgrade', b'proxy-connection', b'transfer-encoding'}:
                    raise ProtocolError('connection-specific header forbidden')
                if name == b'te' and value.lower() != b'trailers':
                    raise ProtocolError('invalid TE header')
            header_map[name] = value
        if b':method' not in pseudo_seen:
            raise ProtocolError('missing :method pseudo-header')
        method = header_map.get(b':method', b'GET')
        protocol = header_map.get(b':protocol')
        if protocol is not None:
            if method != b'CONNECT':
                raise ProtocolError('extended CONNECT requires CONNECT method')
            if b':scheme' not in pseudo_seen or b':path' not in pseudo_seen or b':authority' not in pseudo_seen:
                raise ProtocolError('extended CONNECT missing required pseudo-headers')
            return header_map
        if method == b'CONNECT':
            if b':authority' not in pseudo_seen:
                raise ProtocolError('CONNECT missing :authority pseudo-header')
            if b':scheme' in pseudo_seen or b':path' in pseudo_seen:
                raise ProtocolError('CONNECT must not include :scheme or :path pseudo-headers')
            return header_map
        if b':scheme' not in pseudo_seen or b':path' not in pseudo_seen:
            raise ProtocolError('missing required request pseudo-header')
        return header_map

    async def _invoke_http_app(self, session: HTTP3Session, stream_id: int, request_state: Any, endpoint: UDPEndpoint) -> list[bytes]:
        try:
            header_map = self._validate_request_headers(list(request_state.headers))
            scheme = header_map.get(b':scheme', self.listener.scheme.encode('ascii', 'ignore') if self.listener.scheme else b'https').decode('ascii', 'replace')
        except ProtocolError:
            header_lines = [(b':status', b'400'), (b'content-type', b'text/plain')]
            header_block = session.h3.encode_headers(stream_id, header_lines)
            payload = encode_frame(FRAME_HEADERS, header_block) + encode_frame(FRAME_DATA, b'bad request')
            return [*self._flush_qpack_streams(session), session.quic.send_stream_data(stream_id, payload, fin=True)]
        if not self._admit_stream_work(session, stream_id):
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                503,
                [(b'content-type', b'text/plain')],
                b'scheduler overloaded',
                end_stream=True,
            )
        request = self._build_request(request_state, header_map)
        client = session.addr
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        extensions = {}
        raw_request_trailers = list(getattr(request_state, 'trailers', ()))
        try:
            request_trailers = apply_request_trailer_policy(raw_request_trailers, self.config.http.trailer_policy)
        except ProtocolError:
            self._release_stream_work_lease(session, stream_id)
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                400,
                [(b'content-type', b'text/plain')],
                b'bad request trailers',
                end_stream=True,
            )
        if request.method.upper() == 'CONNECT':
            extensions['tigrcorn.http.connect'] = {'authority': request.target}
        if request_trailers and self.config.http.trailer_policy != 'drop':
            extensions['tigrcorn.http.request_trailers'] = {}
        extensions['tigrcorn.http.response.file'] = {'protocol': 'http/3', 'streaming': True, 'sendfile': False}
        extensions['http.response.pathsend'] = {}
        authority = header_map.get(b':authority')
        if self.config.allowed_server_names and not authority_allowed(authority, self.config.allowed_server_names):
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(client, request.method, request.path, 421, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                421,
                [(b'content-type', b'text/plain')],
                b'misdirected request',
                end_stream=True,
            )
        if self._should_send_too_early(session):
            self._release_stream_work_lease(session, stream_id)
            self.access_logger.log_http(client, request.method, request.path, 425, 'HTTP/3')
            return self._build_http3_response_datagrams_locked(
                session,
                stream_id,
                425,
                [(b'content-type', b'text/plain')],
                b'too early',
                end_stream=True,
            )
        scope = build_http_scope(request, client=client, server=server, scheme=scheme, extensions=extensions, root_path=self.config.proxy.root_path, proxy=self.config.proxy)
        receive = HTTPRequestReceive(request.body, trailers=request_trailers, trailer_policy=self.config.http.trailer_policy)
        send = HTTPResponseCollector()
        status = 500
        try:
            try:
                await self.app(scope, receive, send)
                send.finalize()
                assert send.status is not None
                status = send.status
                headers = list(send.headers)
                trailers = list(send.trailers)
                informational = list(send.informational_responses)
                body_segments = list(send.body_segments) if send.uses_streamed_body else None
                if body_segments is None and send.has_spooled_body():
                    spooled_segments = send.spooled_body_segments()
                    spooled_path = ''
                    if spooled_segments:
                        first_segment = spooled_segments[0]
                        spooled_path = getattr(first_segment, 'path', '')
                    planned = plan_file_backed_response_entity_semantics(
                        method=request.method,
                        request_headers=request.headers,
                        response_headers=headers,
                        status=status,
                        body_path=spooled_path,
                        body_length=send.body_length,
                        generated_etag=send.generated_entity_tag(),
                        apply_content_coding=True,
                        trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                    )
                    if planned.requires_materialization:
                        body = await send.materialize_body()
                        processed = apply_response_entity_semantics(
                            method=request.method,
                            request_headers=request.headers,
                            response_headers=headers,
                            body=body,
                            status=status,
                            content_coding_policy=self.config.http.content_coding_policy,
                            supported_codings=tuple(self.config.http.content_codings),
                            apply_content_coding=True,
                            generate_etag=True,
                        )
                        status = processed.status
                        headers = processed.headers
                        body = processed.body
                        if processed.head_response:
                            trailers = []
                    elif planned.use_body_segments:
                        status = planned.status
                        headers = planned.headers
                        body_segments = list(planned.body_segments)
                        body = b''
                    else:
                        status = planned.status
                        headers = planned.headers
                        body = planned.body
                        trailers = []
                elif body_segments is None:
                    body = await send.materialize_body()
                    processed = apply_response_entity_semantics(
                        method=request.method,
                        request_headers=request.headers,
                        response_headers=headers,
                        body=body,
                        status=status,
                        content_coding_policy=self.config.http.content_coding_policy,
                        supported_codings=tuple(self.config.http.content_codings),
                        apply_content_coding=True,
                        generate_etag=True,
                    )
                    status = processed.status
                    headers = processed.headers
                    body = processed.body
                    if processed.head_response:
                        trailers = []
            except Exception:
                send.cleanup()
                status, headers, body, trailers = 500, [(b'content-type', b'text/plain')], b'internal server error', []
                informational = []
                body_segments = None
            if body_segments is not None:
                await self._send_http3_streamed_response_locked(
                    session,
                    stream_id,
                    status,
                    headers,
                    body_segments,
                    trailers,
                    informational,
                    endpoint,
                )
                self.access_logger.log_http(client, request.method, request.path, status, 'HTTP/3')
                self.sessions[session.addr] = session
                return []
            headers = apply_response_header_policy(
                strip_connection_specific_headers(headers),
                server_header=self.config.server_header_value,
                include_date_header=self.config.include_date_header,
                default_headers=self.config.default_response_headers,
                alt_svc_values=configured_alt_svc_values(self.config, request_http_version='3'),
            )
            frame_payload = bytearray()
            for interim_status, interim_headers in informational:
                interim_header_block = session.h3.encode_headers(
                    stream_id,
                    [(b':status', str(interim_status).encode('ascii')), *sanitize_early_hints_headers(interim_headers)],
                )
                frame_payload.extend(encode_frame(FRAME_HEADERS, interim_header_block))
            header_lines = [(b':status', str(status).encode('ascii')), *headers]
            header_block = session.h3.encode_headers(stream_id, header_lines)
            qpack_outbound = self._flush_qpack_streams(session)
            frame_payload.extend(encode_frame(FRAME_HEADERS, header_block))
            if body:
                frame_payload.extend(encode_frame(FRAME_DATA, body))
            if trailers:
                trailer_block = session.h3.encode_headers(stream_id, list(trailers))
                frame_payload.extend(encode_frame(FRAME_HEADERS, trailer_block))
            self.access_logger.log_http(client, request.method, request.path, status, 'HTTP/3')
            self.sessions[session.addr] = session
            return [*qpack_outbound, session.quic.send_stream_data(stream_id, bytes(frame_payload), fin=True)]
        finally:
            send.cleanup()
            self._release_stream_work_lease(session, stream_id)

    async def _invoke_custom_quic_app(self, session: HTTP3Session, event: Any, endpoint: UDPEndpoint) -> list[bytes]:
        client = session.addr
        local = endpoint.local_addr
        server = (local[0], local[1]) if isinstance(local, tuple) and len(local) >= 2 else ('', None)
        scope = adapt_scope(
            build_custom_scope(
                'tigrcorn.quic',
                scheme=self.listener.scheme or 'quic',
                client=client,
                server=server,
                stream_id=event.stream_id,
                packet_number=event.packet_number,
                extensions={'tigrcorn.custom': {'transport': 'udp', 'protocol': 'quic'}},
            )
        )
        receive = _SingleEventReceive({'type': 'tigrcorn.stream.receive', 'data': event.data, 'more_data': not bool(event.fin)})
        send = _CustomQuicSend(session=session, stream_id=event.stream_id)
        await self.app(scope, receive, send)
        return send.flush()


class _SingleEventReceive:
    def __init__(self, event: dict) -> None:
        self.event = event
        self.sent = False

    async def __call__(self) -> dict:
        if not self.sent:
            self.sent = True
            return self.event
        return {'type': 'tigrcorn.stream.disconnect'}


class _CustomQuicSend:
    def __init__(self, *, session: HTTP3Session, stream_id: int | None) -> None:
        self.session = session
        self.stream_id = 0 if stream_id is None else stream_id
        self.messages: list[bytes] = []

    async def __call__(self, message: dict) -> None:
        typ = message.get('type')
        if typ != 'tigrcorn.stream.send':
            raise RuntimeError(f'unexpected custom quic send event: {typ!r}')
        data = bytes(message.get('data', b''))
        fin = not bool(message.get('more_data', False))
        self.messages.append(self.session.quic.send_stream_data(self.stream_id, data, fin=fin))

    def flush(self) -> list[bytes]:
        return list(self.messages)
