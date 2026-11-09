from __future__ import annotations

from .imports import *

class _TigrCornServerListenerMixin:
    @staticmethod
    def _sync_listener_bound_address(cfg: ListenerConfig, listener: Any) -> None:
        server = getattr(listener, 'server', None)
        sockets = getattr(server, 'sockets', None) if server is not None else None
        if sockets:
            sockname = sockets[0].getsockname()
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                cfg.host = str(sockname[0])
                cfg.port = int(sockname[1])
                return
            if isinstance(sockname, str):
                cfg.path = sockname
                return
        transport = getattr(listener, 'transport', None)
        if transport is not None:
            sockname = transport.get_extra_info('sockname')
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                cfg.host = str(sockname[0])
                cfg.port = int(sockname[1])
                return
            if isinstance(sockname, str):
                cfg.path = sockname
                return

    async def _make_listener(self, cfg: ListenerConfig):
        if cfg.kind == 'tcp':
            ssl_ctx = build_server_ssl_context(cfg)
            return TCPListener(
                cfg.host,
                cfg.port,
                cfg.backlog,
                ssl=ssl_ctx,
                reuse_port=cfg.reuse_port,
                reuse_address=cfg.reuse_address,
                nodelay=cfg.nodelay,
                fd=cfg.fd,
            )
        if cfg.kind == 'udp':
            return UDPListener(cfg.host, cfg.port, reuse_port=cfg.reuse_port, fd=cfg.fd)
        if cfg.kind == 'unix':
            ssl_ctx = build_server_ssl_context(cfg)
            return UnixListener(cfg.path or '', cfg.backlog, ssl=ssl_ctx, fd=cfg.fd)
        if cfg.kind == 'pipe':
            return PipeListener(cfg.path or '')
        return InProcListener()

    def _record_listener_transport_domains(self, listener_cfg: ListenerConfig) -> None:
        for domain_id in self._listener_transport_domain_ids(listener_cfg):
            counters: dict[str, int] = {"connections": 1}
            if domain_id == "quic":
                counters["datagrams"] = 0
                counters["streams"] = 0
            elif domain_id in {"tcp", "unix", "pipe", "in-process"}:
                counters["streams"] = 1
            self._transport_domain_accounting.record(domain_id, **counters)

    def _quic_operational_security_for_listener(self, listener_cfg: ListenerConfig) -> QuicOperationalSecurityRuntime:
        label = listener_cfg.label or f"listener:{len(self._quic_operational_security)}"
        collector = self._quic_operational_security.get(label)
        if collector is None:
            collector = QuicOperationalSecurityRuntime(
                secret=listener_cfg.quic_secret or b"tigrcorn-quic-operational-security",
                profile=self.config.app.profile or "default",
            )
            self._quic_operational_security[label] = collector
        return collector

    def _record_quic_operational_security_packet(
        self,
        listener_cfg: ListenerConfig,
        packet: Any,
        endpoint: Any,
        *,
        attempted_send_bytes: int | None = None,
        address_validated: bool = False,
    ) -> dict[str, Any] | None:
        if "quic" not in listener_cfg.enabled_protocols:
            return None
        packet_bytes = bytes(getattr(packet, "data", packet))
        packet_endpoint = getattr(packet, "addr", endpoint)
        collector = self._quic_operational_security_for_listener(listener_cfg)
        return collector.record_packet_path(
            packet=packet_bytes,
            endpoint=packet_endpoint,
            attempted_send_bytes=attempted_send_bytes,
            address_validated=address_validated,
        )

__all__ = [name for name in globals() if not name.startswith('__')]
