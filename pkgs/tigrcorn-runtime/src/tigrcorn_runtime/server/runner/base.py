from __future__ import annotations

from .imports import *

class _TigrCornServerBase:
    def __init__(self, app: ASGIApp, config: ServerConfig) -> None:
        selection = resolve_app_dispatch(app, config.app.interface)
        self.app = selection.app
        self.app_dispatch_selection = selection
        self.app_interface = selection.interface
        self.app_interface_source = selection.source
        self.app_interface_reason = selection.reason
        self.config = config
        self._resolved_logging = resolve_logging_config(config.log_level, config=config.logging)
        self.logger = configure_logging(config.log_level, config=config.logging)
        self.access_logger = AccessLogger(
            self.logger,
            enabled=self._resolved_logging.access_log,
            fmt=self._resolved_logging.access_log_format,
        )
        self.state = ServerState()
        self.lifespan = LifespanManager(app, mode=config.lifespan)
        self._listeners: list[TCPListener | UDPListener | UnixListener | PipeListener | InProcListener] = []
        self._datagram_handlers: list[HTTP3DatagramHandler] = []
        self._transport_domain_accounting = TransportDomainAccounting()
        self._connection_inventory = RuntimeConnectionInventory()
        self._connection_sequence = 0
        self._quic_operational_security: dict[str, QuicOperationalSecurityRuntime] = {}
        self._quic_congestion_controls: dict[int, Any] = {}
        self._webtransport_governance = WebTransportGovernanceManager(default_webtransport_budget_policy())
        self._should_exit = asyncio.Event()
        self._started = False
        self._metrics_server: asyncio.AbstractServer | None = None
        self._request_budget_task: asyncio.Task[None] | None = None
        self._statsd_exporter = StatsdExporter(config.metrics.statsd_host, logger=self.logger) if config.metrics.statsd_host else None
        self._otel_exporter = OtelExporter(config.metrics.otel_endpoint, logger=self.logger) if config.metrics.otel_endpoint else None
        policy = SchedulerPolicy()
        if config.scheduler.max_connections is not None:
            policy.max_connections = config.scheduler.max_connections
        if config.scheduler.max_tasks is not None:
            policy.max_tasks = config.scheduler.max_tasks
        if config.scheduler.max_streams is not None:
            policy.max_streams_per_session = config.scheduler.max_streams
        if config.scheduler.limit_concurrency is not None:
            policy.limit_concurrency = config.scheduler.limit_concurrency
        self.scheduler = ProductionScheduler(policy)
        self._request_budget = None
        if config.process.limit_max_requests is not None:
            jitter = max(0, config.process.max_requests_jitter)
            self._request_budget = config.process.limit_max_requests + (random.randint(0, jitter) if jitter else 0)

    def _next_connection_id(self, listener_cfg: ListenerConfig) -> str:
        self._connection_sequence += 1
        try:
            listener_index = self.config.listeners.index(listener_cfg)
        except ValueError:
            listener_index = self._connection_sequence
        listener_id = f"listener:{listener_index}"
        return f"conn:{listener_id}:{self._connection_sequence}"

    @staticmethod
    def _address_string(address: Any) -> str | None:
        if isinstance(address, tuple) and len(address) >= 2:
            return f"{address[0]}:{address[1]}"
        if isinstance(address, str):
            return address
        return None

__all__ = [name for name in globals() if not name.startswith('__')]
