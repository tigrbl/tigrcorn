from __future__ import annotations

from .imports import *

class HTTP3RequestsMixin:
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
            return [*self._flush_qpack_streams(session), *session.quic.send_stream_data_packets(stream_id, payload, fin=True)]
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
        inventory_session_id = None
        if self.connection_inventory is not None:
            inventory_session_id = f"{self._connection_id_for_session(session)}:http3:{stream_id}"
            self.connection_inventory.open_session(
                inventory_session_id,
                connection_id=self._connection_id_for_session(session),
                kind='http-request',
                stream_ids=(str(stream_id),),
                metadata={'method': request.method, 'path': request.path, 'protocol': 'http3'},
            )
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
                if self.metrics is not None:
                    self.metrics.http3_request_served()
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
            if self.metrics is not None:
                self.metrics.http3_request_served()
            return [*qpack_outbound, *session.quic.send_stream_data_packets(stream_id, bytes(frame_payload), fin=True)]
        finally:
            if self.connection_inventory is not None and inventory_session_id is not None:
                self.connection_inventory.increment_session_counter(inventory_session_id, 'responses')
                self.connection_inventory.close_session(inventory_session_id, reason='request-complete')
            send.cleanup()
            self._release_stream_work_lease(session, stream_id)
