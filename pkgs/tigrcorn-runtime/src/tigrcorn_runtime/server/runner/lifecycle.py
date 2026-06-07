from __future__ import annotations

from .imports import *

class _TigrCornServerLifecycleMixin:
    async def start(self) -> None:
        if self._started:
            return
        if self.config.app.profile and self.config.app.profile != "default":
            validate_profile_transport_domains(
                self.config.app.profile,
                required_domains=self._configured_transport_domain_ids(),
            )
        with span('server.start', attrs={'listener_count': len(self.config.listeners)}, sink=self._otel_exporter.record_span if self._otel_exporter is not None else None):
            try:
                await self.lifespan.startup()
                await run_async_hooks(self.config.hooks.on_startup, self)
                for listener_cfg in self.config.listeners:
                    listener = await self._make_listener(listener_cfg)
                    await listener.start(self._make_client_handler(listener_cfg))
                    self._sync_listener_bound_address(listener_cfg, listener)
                    self._listeners.append(listener)
                    self._record_listener_transport_domains(listener_cfg)
                    self.logger.info('listening on %s', listener_cfg.label)
                if self.config.metrics.enabled and self.config.metrics.bind:
                    self._metrics_server = await self._start_metrics_endpoint(self.config.metrics.bind)
                if self._statsd_exporter is not None:
                    await self._statsd_exporter.start(self.state.metrics)
                if self._otel_exporter is not None:
                    await self._otel_exporter.start(self.state.metrics)
                if self._request_budget is not None:
                    self._request_budget_task = asyncio.create_task(self._monitor_request_budget(), name='tigrcorn-request-budget')
            except Exception:
                await self.close()
                raise
        self._started = True

    def resource_ownership(self) -> dict[str, Any]:
        resources: list[dict[str, Any]] = [
            {
                "id": "runtime:event-loop",
                "kind": "event_loop",
                "owner": "caller",
                "caller_owned": True,
                "active": self._started,
                "close_action": "not_closed",
            },
            {
                "id": "runtime:worker-pool",
                "kind": "worker_pool",
                "owner": "tigrcorn",
                "caller_owned": False,
                "active": self._started and self.config.process.workers > 1,
                "close_action": "shutdown",
            },
        ]
        for index, listener in enumerate(self.config.listeners):
            active = self._started and index < len(self._listeners)
            resources.append(
                {
                    "id": f"listener:{index}",
                    "kind": "listener",
                    "owner": "tigrcorn",
                    "caller_owned": False,
                    "active": active,
                    "close_action": "close",
                    "label": listener.label,
                }
            )
            resources.append(
                {
                    "id": f"socket:{index}",
                    "kind": "socket",
                    "owner": "tigrcorn" if listener.fd is None else "caller",
                    "caller_owned": listener.fd is not None,
                    "active": active and listener.kind in {"tcp", "udp", "unix"},
                    "close_action": "close" if listener.fd is None else "not_closed",
                    "label": listener.label,
                }
            )
            resources.append(
                {
                    "id": f"transport:{index}",
                    "kind": "transport",
                    "owner": "tigrcorn",
                    "caller_owned": False,
                    "active": active,
                    "close_action": "close",
                    "label": listener.kind,
                }
            )
            if listener.ssl_certfile or listener.ssl_keyfile or listener.alpn_protocols:
                resources.append(
                    {
                        "id": f"tls-context:{index}",
                        "kind": "tls_context",
                        "owner": "tigrcorn",
                        "caller_owned": False,
                        "active": active and listener.ssl_enabled,
                        "close_action": "release",
                        "label": "<redacted>",
                    }
                )
        resources.append(
            {
                "id": "telemetry:statsd",
                "kind": "telemetry_exporter",
                "owner": "tigrcorn",
                "caller_owned": False,
                "active": self._statsd_exporter is not None and getattr(self._statsd_exporter, "_task", None) is not None,
                "close_action": "flush_stop",
            }
        )
        resources.append(
            {
                "id": "telemetry:otel",
                "kind": "telemetry_exporter",
                "owner": "tigrcorn",
                "caller_owned": False,
                "active": self._otel_exporter is not None and getattr(self._otel_exporter, "_task", None) is not None,
                "close_action": "flush_stop",
            }
        )
        return {
            "schema_version": "1.0",
            "owner": "tigrcorn",
            "generation": int(self.state.shutting_down) + int(self._started),
            "active": self._started and not self.state.shutting_down,
            "resources": sorted(resources, key=lambda item: item["id"]),
        }

    async def serve_forever(self) -> None:
        await self.start()
        try:
            await self._should_exit.wait()
        finally:
            await self.close()


    def request_shutdown(self) -> None:
        self._should_exit.set()

    async def close(self) -> None:
        if self.state.shutting_down:
            return
        self.state.shutting_down = True
        with span('server.shutdown', attrs={'active_listeners': len(self._listeners)}, sink=self._otel_exporter.record_span if self._otel_exporter is not None else None):
            if self._request_budget_task is not None:
                self._request_budget_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await self._request_budget_task
                self._request_budget_task = None
            if self._metrics_server is not None:
                self._metrics_server.close()
                with suppress(Exception):
                    await self._metrics_server.wait_closed()
                self._metrics_server = None
            for listener in self._listeners:
                with suppress(Exception):
                    await listener.close()
            self._listeners.clear()
            for handler in self._datagram_handlers:
                with suppress(Exception):
                    await handler.close()
            self._datagram_handlers.clear()
            with suppress(Exception):
                await asyncio.wait_for(self.scheduler.close(), timeout=self.config.http.shutdown_timeout)
            with suppress(Exception):
                await self.lifespan.shutdown()
            with suppress(Exception):
                await run_async_hooks(self.config.hooks.on_shutdown, self)
        if self._statsd_exporter is not None:
            with suppress(Exception):
                await self._statsd_exporter.stop(self.state.metrics)
        if self._otel_exporter is not None:
            with suppress(Exception):
                await self._otel_exporter.stop(self.state.metrics)

__all__ = [name for name in globals() if not name.startswith('__')]
