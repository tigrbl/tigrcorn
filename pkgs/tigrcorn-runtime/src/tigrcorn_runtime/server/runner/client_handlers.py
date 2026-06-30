from __future__ import annotations

from .imports import *

class _TigrCornServerClientHandlerMixin:
    def _make_client_handler(self, listener_cfg: ListenerConfig):
        if listener_cfg.kind == 'udp':
            h3_handler = HTTP3DatagramHandler(
                app=self.app,
                config=self.config,
                listener=listener_cfg,
                access_logger=self.access_logger,
                scheduler=self.scheduler,
                metrics=self.state.metrics,
                webtransport_governance=self._webtransport_governance,
                connection_inventory=self._connection_inventory,
            )
            self._datagram_handlers.append(h3_handler)

            async def udp_handler(packet, endpoint) -> None:
                sessions_before = len(h3_handler.sessions)
                responses_before = sum(len(session.responded_streams) for session in h3_handler.sessions.values())
                self._record_quic_operational_security_packet(listener_cfg, packet, endpoint)
                await h3_handler.handle_packet(packet, endpoint)
                if len(h3_handler.sessions) > sessions_before:
                    self.state.metrics.connection_opened()
                responses_after = sum(len(session.responded_streams) for session in h3_handler.sessions.values())
                if responses_after > responses_before:
                    self.state.metrics.requests_served += responses_after - responses_before

            return udp_handler

        if listener_cfg.kind == 'pipe':
            raw_handler = RawFramedApplicationHandler(
                app=self.app,
                config=self.config,
                listener=listener_cfg,
                access_logger=self.access_logger,
            )

            async def pipe_handler(connection, data) -> None:
                handled = await raw_handler.feed_bytes(connection, data, path=listener_cfg.path)
                self.state.metrics.requests_served += handled
                self.state.metrics.bytes_received += len(data)

            return pipe_handler

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await self._handle_client(reader, writer, listener_cfg)

        return handler

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        listener_cfg: ListenerConfig,
    ) -> None:
        lease = self.scheduler.acquire_connection()
        if lease is None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return
        self.state.metrics.connection_opened()
        peername = writer.get_extra_info('peername')
        sockname = writer.get_extra_info('sockname')
        ssl_obj = writer.get_extra_info('ssl_object')
        selected_alpn = ssl_obj.selected_alpn_protocol() if ssl_obj else None
        tls_payload = tls_extension_payload(writer)
        scope_tls_extensions = {'tls': tls_payload} if tls_payload is not None else None
        client_host, client_port = peer_parts(peername)
        server_host, server_port = peer_parts(sockname)
        client = (client_host, client_port) if client_host is not None and client_port is not None else None
        server = (server_host or '', server_port)
        scheme = 'https' if ssl_obj else (listener_cfg.scheme or 'http')
        ws_scheme = 'wss' if ssl_obj else 'ws'
        connection_id = self._next_connection_id(listener_cfg)
        remote_address = self._address_string(peername)
        local_address = self._address_string(sockname)
        listener_index = self.config.listeners.index(listener_cfg) if listener_cfg in self.config.listeners else 0
        self._connection_inventory.open_connection(
            connection_id,
            transport=listener_cfg.kind,
            protocols=tuple(sorted(listener_cfg.enabled_protocols)),
            listener_id=f"listener:{listener_index}",
            peer_id=peer_id_from_address(remote_address),
            remote_address=remote_address,
            local_address=local_address,
            security={"alpn": selected_alpn, "tls": bool(ssl_obj)},
        )
        try:
            if selected_alpn == 'h2' and '2' in listener_cfg.http_versions:
                h2_handler = HTTP2ConnectionHandler(
                    app=self.app,
                    config=self.config,
                    access_logger=self.access_logger,
                    scheduler=self.scheduler,
                    metrics=self.state.metrics,
                    reader=reader,
                    writer=writer,
                    client=client,
                    server=server,
                    scheme=scheme,
                    scope_extensions=scope_tls_extensions,
                    connection_id=connection_id,
                    connection_inventory=self._connection_inventory,
                )
                await h2_handler.handle()
                return

            initial = b''
            if '2' in listener_cfg.http_versions and self.config.enable_h2c:
                initial = await self._read_preface_probe(reader)
                if initial == H2_PREFACE:
                    h2_handler = HTTP2ConnectionHandler(
                        app=self.app,
                        config=self.config,
                        access_logger=self.access_logger,
                        scheduler=self.scheduler,
                        metrics=self.state.metrics,
                        reader=reader,
                        writer=writer,
                        client=client,
                        server=server,
                        scheme=scheme,
                        prebuffer=initial,
                        scope_extensions=scope_tls_extensions,
                        connection_id=connection_id,
                        connection_inventory=self._connection_inventory,
                    )
                    await h2_handler.handle()
                    return

            buffered_reader: StreamReaderLike = PrebufferedReader(reader, initial)
            await self._handle_http11_connection(
                buffered_reader,
                writer,
                listener_cfg,
                client=client,
                server=server,
                scheme=scheme,
                ws_scheme=ws_scheme,
                scope_extensions=scope_tls_extensions,
                connection_id=connection_id,
            )
        finally:
            self._connection_inventory.close_connection(connection_id, reason='client-handler-complete')
            lease.release()
            self.state.metrics.connection_closed()
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

__all__ = [name for name in globals() if not name.startswith('__')]
