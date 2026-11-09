from __future__ import annotations

from .imports import *

class _TigrCornServerMetricsMixin:
    @staticmethod
    def _writer_tls_observability(writer: asyncio.StreamWriter) -> dict[str, str | None]:
        ssl_object = writer.get_extra_info("ssl_object")
        if ssl_object is None:
            return {"tls_version": None, "alpn": None}
        version = getattr(ssl_object, "version", lambda: None)()
        alpn = getattr(ssl_object, "selected_alpn_protocol", lambda: None)()
        return {"tls_version": version, "alpn": alpn}

    async def _start_metrics_endpoint(self, bind: str) -> asyncio.AbstractServer:
        host, port = self._parse_bind_target(bind)
        server = await asyncio.start_server(self._handle_metrics_request, host=host, port=port)
        self.logger.info('metrics endpoint listening on %s', bind)
        return server

    async def _handle_metrics_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with suppress(Exception):
            await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=1.0)
        payload = self.state.metrics.render_prometheus().encode('utf-8')
        response = serialize_http11_response_whole(
            status=200,
            headers=[(b'content-type', b'text/plain; version=0.0.4')],
            body=payload,
            keep_alive=False,
            server_header=self.config.server_header_value,
            include_date_header=self.config.include_date_header,
            default_headers=self.config.default_response_headers,
        )
        writer.write(response)
        with suppress(Exception):
            await writer.drain()
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    @staticmethod
    @staticmethod
    def _parse_bind_target(bind: str) -> tuple[str, int]:
        if bind.startswith('[') and ']:' in bind:
            host, port = bind.rsplit(':', 1)
            return host[1:-1], int(port)
        host, port = bind.rsplit(':', 1)
        return host, int(port)

    async def _monitor_request_budget(self) -> None:
        assert self._request_budget is not None
        while not self._should_exit.is_set() and not self.state.shutting_down:
            if self.state.metrics.requests_served >= self._request_budget:
                self.logger.info('request budget reached, shutting down worker')
                self.request_shutdown()
                return
            await asyncio.sleep(0.1)

__all__ = [name for name in globals() if not name.startswith('__')]
