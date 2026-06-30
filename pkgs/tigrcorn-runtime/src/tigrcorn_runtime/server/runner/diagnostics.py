from __future__ import annotations

from .imports import *

class _TigrCornServerDiagnosticsMixin:
    def describe(self) -> dict[str, Any]:
        configured_protocols: set[str] = set()
        configured_transports: set[str] = set()
        listeners: list[dict[str, Any]] = []
        bound_endpoints = self._bound_endpoint_strings()
        for index, listener in enumerate(self.config.listeners):
            protocols = tuple(sorted(listener.enabled_protocols))
            configured_protocols.update(protocols)
            configured_transports.add(listener.kind)
            listeners.append(
                {
                    "id": f"listener:{index}",
                    "active": self._started and index < len(self._listeners),
                    "kind": listener.kind,
                    "label": listener.label,
                    "bound_endpoint": bound_endpoints[index] if index < len(bound_endpoints) else None,
                    "protocols": list(protocols),
                    "http_versions": list(listener.http_versions),
                    "tls": {
                        "enabled": listener.ssl_enabled,
                        "alpn_protocols": list(listener.alpn_protocols),
                        "certfile": self._redact(listener.ssl_certfile),
                        "keyfile": self._redact(listener.ssl_keyfile),
                        "ca_certs": self._redact(listener.ssl_ca_certs),
                        "client_cert_required": bool(listener.ssl_require_client_cert),
                        "ocsp_mode": listener.ocsp_mode,
                        "crl_mode": listener.crl_mode,
                    },
                }
            )
        return {
            "schema_version": "1.0",
            "runtime": self.config.process.runtime,
            "active": self._started,
            "profile": self.config.app.profile or "default",
            "app_interface": {
                "selected": self.app_interface,
                "source": self.app_interface_source,
                "reason": self.app_interface_reason,
            },
            "capabilities": {
                "protocols": ["http1", "http2", "http3", "lifespan", "quic", "websocket", "webtransport"],
                "transports": sorted(TRANSPORTS),
            },
            "configured_protocols": sorted(configured_protocols),
            "active_protocols": sorted(configured_protocols) if self._started else [],
            "configured_transports": sorted(configured_transports),
            "active_transports": sorted(configured_transports) if self._started else [],
            "transport_domains": self.transport_domain_diagnostics(),
            "connection_inventory": self.connection_inventory(),
            "quic_operational_security": self.quic_operational_security_evidence(),
            "webtransport_resource_governance": self.webtransport_resource_governance(),
            "listeners": listeners,
            "worker": {
                "count": self.config.process.workers,
                "class": self.config.process.worker_class,
                "runtime": self.config.process.runtime,
            },
            "observability": {
                "metrics_enabled": bool(self.config.metrics.enabled),
                "metrics_bind": self.config.metrics.bind,
                "statsd_enabled": bool(self.config.metrics.statsd_host),
                "otel_enabled": bool(self.config.metrics.otel_endpoint),
                "structured_logging": bool(self.config.logging.structured),
            },
        }

    def _bound_endpoint_strings(self) -> list[str]:
        endpoints: list[str] = []
        for listener in self._listeners:
            server = getattr(listener, "server", None)
            sockets = getattr(server, "sockets", None) if server is not None else None
            if sockets:
                endpoints.append(str(sockets[0].getsockname()))
                continue
            transport = getattr(listener, "transport", None)
            if transport is not None:
                sockname = transport.get_extra_info("sockname")
                if sockname is not None:
                    endpoints.append(str(sockname))
                    continue
            path = getattr(listener, "path", None)
            if path:
                endpoints.append(str(path))
        return endpoints

    def transport_domain_diagnostics(self) -> dict[str, Any]:
        active_domains = self._active_transport_domain_ids() if self._started else ()
        return transport_domain_diagnostics(
            accounting=self._transport_domain_accounting,
            active_domains=active_domains,
            endpoint_identities=self._transport_domain_endpoint_identities(active_domains),
        )

    def quic_operational_security_evidence(self) -> dict[str, Any]:
        return {
            label: collector.runtime_evidence()
            for label, collector in sorted(self._quic_operational_security.items())
        }

    def connection_inventory(self) -> dict[str, Any]:
        return self._jsonable(self._connection_inventory.snapshot())

    def webtransport_resource_governance(self) -> dict[str, Any]:
        return self._jsonable(self._webtransport_governance.snapshot())

    def _active_transport_domain_ids(self) -> tuple[str, ...]:
        domains: set[str] = set()
        for index, listener in enumerate(self.config.listeners):
            if index >= len(self._listeners):
                continue
            domains.update(self._listener_transport_domain_ids(listener))
        return tuple(sorted(domains))

    def _configured_transport_domain_ids(self) -> tuple[str, ...]:
        domains: set[str] = set()
        for listener in self.config.listeners:
            domains.update(self._listener_transport_domain_ids(listener))
        return tuple(sorted(domains))

    @staticmethod
    def _listener_transport_domain_ids(listener: ListenerConfig) -> tuple[str, ...]:
        domains = {"listener", _normalize_listener_kind(listener.kind)}
        if "quic" in listener.enabled_protocols:
            domains.add("quic")
        return tuple(sorted(domains))

    def _transport_domain_endpoint_identities(self, active_domains: Iterable[str]) -> dict[str, str | None]:
        endpoint = ",".join(self._bound_endpoint_strings()) or None
        return {domain_id: endpoint for domain_id in active_domains}

    @staticmethod
    def _redact(value: Any) -> str | None:
        return "<redacted>" if value else None

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, tuple):
            return [_TigrCornServerDiagnosticsMixin._jsonable(item) for item in value]
        if isinstance(value, list):
            return [_TigrCornServerDiagnosticsMixin._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {
                key: _TigrCornServerDiagnosticsMixin._jsonable(item)
                for key, item in value.items()
            }
        return value

__all__ = [name for name in globals() if not name.startswith('__')]
