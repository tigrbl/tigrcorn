from __future__ import annotations

from .imports import *

class _TigrCornServerHTTP11ServeMixin:
    async def _serve_http11_request(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        request: ParsedRequestHead,
        *,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        scope_extensions: dict | None = None,
    ) -> bool:
        host_header = get_header(request.headers, b'host')
        if self.config.allowed_server_names and not authority_allowed(host_header, self.config.allowed_server_names):
            await self._write_error(writer, 421, b'misdirected request', keep_alive=False)
            return False
        scope = build_http_scope(
            request,
            client=client,
            server=server,
            scheme=scheme,
            extensions=self._http11_scope_extensions(request, scope_extensions=scope_extensions),
            root_path=self.config.proxy.root_path,
            proxy=self.config.proxy,
        )
        receive = self._build_http11_receive(reader, writer, request)
        send = HTTPResponseCollector()
        status = 500
        trailers: list[tuple[bytes, bytes]] = []
        try:
            await self.app(scope, receive, send)
            send.finalize()
            assert send.status is not None
            status = send.status
            headers = list(send.headers)
            trailers = list(send.trailers)
            body = b''
            body_segments = list(send.body_segments) if send.uses_streamed_body else None
            for interim_status, interim_headers in send.informational_responses:
                writer.write(
                    serialize_http11_response_head(
                        status=interim_status,
                        headers=interim_headers,
                        keep_alive=request.keep_alive,
                        server_header=self.config.server_header_value,
                        chunked=False,
                        include_date_header=self.config.include_date_header,
                        default_headers=self.config.default_response_headers,
                        alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                    )
                )
            if body_segments is None and send.has_spooled_body():
                spooled_segments = send.spooled_body_segments()
                spooled_path = ''
                if spooled_segments:
                    first_segment = spooled_segments[0]
                    if isinstance(first_segment, FileBodySegment):
                        spooled_path = first_segment.path
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
                        trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
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
                    trailers_present=bool(trailers) and request.method.upper() != 'HEAD',
                )
                status = processed.status
                headers = processed.headers
                body = processed.body
                if processed.head_response:
                    trailers = []
            if body_segments is None:
                if trailers:
                    writer.write(
                        serialize_http11_response_head(
                            status=status,
                            headers=headers,
                            keep_alive=request.keep_alive,
                            server_header=self.config.server_header_value,
                            chunked=True,
                            include_date_header=self.config.include_date_header,
                            default_headers=self.config.default_response_headers,
                            alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                        )
                    )
                    if body:
                        writer.write(serialize_http11_response_chunk(body))
                    writer.write(finalize_chunked_body(trailers))
                    await self._drain_writer(writer)
                else:
                    writer.write(
                        serialize_http11_response_whole(
                            status=status,
                            headers=headers,
                            body=body,
                            keep_alive=request.keep_alive,
                            server_header=self.config.server_header_value,
                            include_date_header=self.config.include_date_header,
                            default_headers=self.config.default_response_headers,
                            alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                        )
                    )
                    await self._drain_writer(writer)
            else:
                await self._send_http11_streamed_response(
                    writer,
                    request=request,
                    status=status,
                    headers=headers,
                    body_segments=body_segments,
                    trailers=trailers,
                )
            self.state.metrics.requests_served += 1
        except ProtocolError:
            self.state.metrics.requests_failed += 1
            await self._write_error(writer, 400, b'bad request trailers', keep_alive=False)
            return False
        except Exception:
            self.state.metrics.requests_failed += 1
            self.logger.exception('application error')
            await self._write_error(writer, 500, b'internal server error', keep_alive=False)
            return False
        finally:
            send.cleanup()
        self.access_logger.log_http(
            client,
            request.method,
            request.path,
            status,
            f'HTTP/{request.http_version}',
            request_headers=request.headers,
            **self._writer_tls_observability(writer),
        )
        body_complete = getattr(receive, 'body_complete', True)
        return request.keep_alive and body_complete

    async def _write_error(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        body: bytes,
        *,
        keep_alive: bool,
    ) -> None:
        writer.write(
            serialize_http11_response_whole(
                status=status,
                headers=[(b'content-type', b'text/plain; charset=utf-8')],
                body=body,
                keep_alive=keep_alive,
                server_header=self.config.server_header_value,
                include_date_header=self.config.include_date_header,
                default_headers=self.config.default_response_headers,
                alt_svc_values=configured_alt_svc_values(self.config, request_http_version='1.1'),
            )
        )
        await self._drain_writer(writer)

__all__ = [name for name in globals() if not name.startswith('__')]
