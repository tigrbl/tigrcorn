from __future__ import annotations

from .imports import *

class _TigrCornServerHTTP11SendMixin:
    async def _try_http11_sendfile(self, writer: asyncio.StreamWriter, segment: FileBodySegment) -> bool:
        if segment.count is not None and segment.count <= 0:
            return True
        if writer.get_extra_info('ssl_object') is not None or writer.get_extra_info('sslcontext') is not None:
            return False
        transport = getattr(writer, 'transport', None) or getattr(writer, '_transport', None)
        if transport is None:
            return False
        loop = asyncio.get_running_loop()
        try:
            with open(segment.path, 'rb') as handle:
                await loop.sendfile(transport, handle, offset=segment.offset, count=segment.count, fallback=False)
            return True
        except Exception:
            return False

    async def _send_http11_body_segments(self, writer: asyncio.StreamWriter, body_segments: list, *, chunked: bool = False) -> None:
        if not chunked and len(body_segments) == 1 and isinstance(body_segments[0], FileBodySegment):
            if await self._try_http11_sendfile(writer, body_segments[0]):
                return
        async for chunk in iter_response_body_segments(body_segments):
            self.state.metrics.bytes_sent += len(chunk)
            if chunked:
                writer.write(serialize_http11_response_chunk(chunk))
            else:
                writer.write(chunk)
            if len(chunk) >= 64 * 1024:
                await self._drain_writer(writer)
        await self._drain_writer(writer)

    async def _send_http11_streamed_response(
        self,
        writer: asyncio.StreamWriter,
        *,
        request: ParsedRequestHead,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body_segments: list,
        trailers: list[tuple[bytes, bytes]],
    ) -> None:
        has_body = response_body_segments_have_bytes(body_segments)
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
            await self._drain_writer(writer)
            if has_body:
                await self._send_http11_body_segments(writer, body_segments, chunked=True)
            writer.write(finalize_chunked_body(trailers))
            await self._drain_writer(writer)
            return
        if not has_body:
            writer.write(
                serialize_http11_response_whole(
                    status=status,
                    headers=headers,
                    body=b'',
                    keep_alive=request.keep_alive,
                    server_header=self.config.server_header_value,
                    include_date_header=self.config.include_date_header,
                    default_headers=self.config.default_response_headers,
                    alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
                )
            )
            await self._drain_writer(writer)
            return
        writer.write(
            serialize_http11_response_head(
                status=status,
                headers=headers,
                keep_alive=request.keep_alive,
                server_header=self.config.server_header_value,
                chunked=False,
                include_date_header=self.config.include_date_header,
                default_headers=self.config.default_response_headers,
                alt_svc_values=configured_alt_svc_values(self.config, request_http_version=request.http_version),
            )
        )
        await self._drain_writer(writer)
        await self._send_http11_body_segments(writer, body_segments, chunked=False)

    async def _handle_http11_connect_tunnel(
        self,
        reader: StreamReaderLike,
        writer: asyncio.StreamWriter,
        request: ParsedRequestHead,
        *,
        client: tuple[str, int] | None,
    ) -> None:
        try:
            host, port = self._parse_connect_authority(request.target)
        except Exception:
            await self._write_error(writer, 400, b'bad connect target', keep_alive=False)
            return
        if self.config.http.connect_policy == 'deny':
            await self._write_error(writer, 403, b'connect denied', keep_alive=False)
            return
        if self.config.http.connect_policy == 'allowlist' and not is_connect_allowed(host, port, self.config.http.connect_allow):
            await self._write_error(writer, 403, b'connect denied', keep_alive=False)
            return
        if request.body_kind != 'none':
            await self._write_error(writer, 400, b'connect request body not supported', keep_alive=False)
            return
        work_lease = self.scheduler.acquire_work()
        if work_lease is None:
            self.state.metrics.scheduler_task_rejected()
            await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=self.config.http.read_timeout)
        except Exception:
            work_lease.release()
            await self._write_error(writer, 502, b'bad gateway', keep_alive=False)
            return
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await self._drain_writer(writer)
        self.access_logger.log_http(client, 'CONNECT', request.target, 200, f'HTTP/{request.http_version}')
        try:
            self.state.metrics.scheduler_task_spawned()
            relay_up = self.scheduler.spawn(self._relay_stream(reader, upstream_writer), owner=f'connect:{request.target}:up')
            self.state.metrics.scheduler_task_spawned()
            relay_down = self.scheduler.spawn(self._relay_stream(upstream_reader, writer), owner=f'connect:{request.target}:down')
        except RuntimeError:
            self.state.metrics.scheduler_task_rejected()
            await self._write_error(writer, 503, b'scheduler overloaded', keep_alive=False)
            return
        try:
            done, pending = await asyncio.wait({relay_up, relay_down}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                with suppress(Exception):
                    await task
            for task in done:
                with suppress(Exception):
                    await task
        finally:
            work_lease.release()

__all__ = [name for name in globals() if not name.startswith('__')]
