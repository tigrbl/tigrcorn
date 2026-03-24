from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from time import monotonic, time
from typing import Any, Mapping


@dataclass(slots=True)
class Metrics:
    started_at: float = field(default_factory=monotonic)
    connections_opened: int = 0
    connections_closed: int = 0
    active_connections: int = 0
    requests_served: int = 0
    requests_failed: int = 0
    websocket_connections: int = 0
    websocket_connections_closed: int = 0
    active_websocket_connections: int = 0
    scheduler_tasks_spawned: int = 0
    scheduler_tasks_rejected: int = 0
    scheduler_rejections: int = 0
    streams_opened: int = 0
    websocket_pings_sent: int = 0
    websocket_ping_timeouts: int = 0
    protocol_errors: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0

    def connection_opened(self) -> None:
        self.connections_opened += 1
        self.active_connections += 1

    def connection_closed(self) -> None:
        self.connections_closed += 1
        self.active_connections = max(0, self.active_connections - 1)

    def websocket_opened(self) -> None:
        self.websocket_connections += 1
        self.active_websocket_connections += 1

    def websocket_closed(self) -> None:
        self.websocket_connections_closed += 1
        self.active_websocket_connections = max(0, self.active_websocket_connections - 1)

    def scheduler_task_spawned(self) -> None:
        self.scheduler_tasks_spawned += 1

    def scheduler_task_rejected(self) -> None:
        self.scheduler_tasks_rejected += 1
        self.scheduler_rejections += 1

    def websocket_ping_sent(self) -> None:
        self.websocket_pings_sent += 1

    def websocket_ping_timeout(self) -> None:
        self.websocket_ping_timeouts += 1

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, monotonic() - self.started_at)

    def snapshot(self) -> dict[str, Any]:
        return {
            'uptime_seconds': round(self.uptime_seconds, 6),
            'connections_opened': self.connections_opened,
            'connections_closed': self.connections_closed,
            'active_connections': self.active_connections,
            'requests_served': self.requests_served,
            'requests_failed': self.requests_failed,
            'websocket_connections': self.websocket_connections,
            'websocket_connections_closed': self.websocket_connections_closed,
            'active_websocket_connections': self.active_websocket_connections,
            'scheduler_tasks_spawned': self.scheduler_tasks_spawned,
            'scheduler_tasks_rejected': self.scheduler_tasks_rejected,
            'scheduler_rejections': self.scheduler_rejections,
            'streams_opened': self.streams_opened,
            'websocket_pings_sent': self.websocket_pings_sent,
            'websocket_ping_timeouts': self.websocket_ping_timeouts,
            'protocol_errors': self.protocol_errors,
            'bytes_received': self.bytes_received,
            'bytes_sent': self.bytes_sent,
        }

    def render_prometheus(self, *, prefix: str = 'tigrcorn') -> str:
        snapshot = self.snapshot()
        lines = []
        for key, value in snapshot.items():
            metric_name = f"{prefix}_{key}"
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")
        return '\n'.join(lines) + '\n'

    def render_statsd(self, *, prefix: str = 'tigrcorn', previous: Mapping[str, Any] | None = None) -> str:
        return '\n'.join(iter_statsd_lines(self.snapshot(), previous=previous, prefix=prefix))


def _is_gauge_metric(name: str) -> bool:
    return name.startswith('active_') or name == 'uptime_seconds'


def iter_statsd_lines(snapshot: Mapping[str, Any], *, previous: Mapping[str, Any] | None = None, prefix: str = 'tigrcorn') -> list[str]:
    lines: list[str] = []
    previous = previous or {}
    for key, raw_value in snapshot.items():
        metric_name = f'{prefix}.{key}'
        if _is_gauge_metric(key):
            lines.append(f'{metric_name}:{raw_value}|g')
            continue
        current = float(raw_value)
        baseline = float(previous.get(key, 0))
        delta = current - baseline
        if delta < 0:
            delta = current
        lines.append(f'{metric_name}:{delta}|c')
    return lines


def parse_statsd_host(target: str) -> tuple[str, int]:
    target = str(target).strip()
    if not target:
        raise ValueError('statsd_host cannot be empty')
    if target.startswith('[') and ']:' in target:
        host, port = target.rsplit(':', 1)
        host = host[1:-1]
    elif ':' in target:
        host, port = target.rsplit(':', 1)
    else:
        raise ValueError('statsd_host must be host:port')
    port_value = int(port)
    if port_value <= 0 or port_value > 65535:
        raise ValueError('statsd_host port must be between 1 and 65535')
    if not host:
        raise ValueError('statsd_host host cannot be empty')
    return host, port_value


class StatsdExporter:
    def __init__(self, target: str, *, prefix: str = 'tigrcorn', interval: float = 1.0, logger: logging.Logger | None = None) -> None:
        self.host, self.port = parse_statsd_host(target)
        self.prefix = prefix
        self.interval = max(0.1, float(interval))
        self.logger = logger
        self._task: asyncio.Task[None] | None = None
        self._socket: socket.socket | None = None
        self._sockaddr: tuple[Any, ...] | None = None
        self._last_snapshot: dict[str, Any] | None = None
        self.sent_packets = 0
        self.send_failures = 0
        self.last_payload: str | None = None
        self.last_error: str | None = None

    def _ensure_socket(self) -> socket.socket:
        if self._socket is not None:
            return self._socket
        infos = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_DGRAM)
        family, socktype, proto, _canon, sockaddr = infos[0]
        sock = socket.socket(family, socktype, proto)
        sock.setblocking(False)
        self._socket = sock
        self._sockaddr = sockaddr
        return sock

    async def start(self, metrics: Metrics) -> None:
        if self._task is not None:
            return
        await self.export_now(metrics)
        self._task = asyncio.create_task(self._run(metrics), name='tigrcorn-statsd-exporter')

    async def _run(self, metrics: Metrics) -> None:
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self.export_now(metrics)
        except asyncio.CancelledError:
            raise

    async def export_now(self, metrics: Metrics) -> None:
        snapshot = metrics.snapshot()
        payload = '\n'.join(iter_statsd_lines(snapshot, previous=self._last_snapshot, prefix=self.prefix))
        self._last_snapshot = dict(snapshot)
        self.last_payload = payload
        if not payload:
            return
        try:
            sock = self._ensure_socket()
            assert self._sockaddr is not None
            await asyncio.get_running_loop().sock_sendto(sock, payload.encode('utf-8'), self._sockaddr)
            self.sent_packets += 1
        except Exception as exc:  # pragma: no cover - bounded failure path exercised in tests
            self.send_failures += 1
            self.last_error = str(exc)
            if self.logger is not None:
                self.logger.warning('statsd exporter send failed: %s', exc)

    async def stop(self, metrics: Metrics | None = None) -> None:
        if metrics is not None:
            await self.export_now(metrics)
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None
                self._sockaddr = None


def otel_metric_payload(snapshot: Mapping[str, Any], *, prefix: str = 'tigrcorn') -> list[dict[str, Any]]:
    now_nanos = str(int(time() * 1_000_000_000))
    metrics_payload: list[dict[str, Any]] = []
    for key, value in snapshot.items():
        name = f'{prefix}.{key}'
        if _is_gauge_metric(key):
            metrics_payload.append({
                'name': name,
                'gauge': {
                    'dataPoints': [{'timeUnixNano': now_nanos, 'asDouble': float(value)}],
                },
            })
        else:
            metrics_payload.append({
                'name': name,
                'sum': {
                    'aggregationTemporality': 2,
                    'isMonotonic': True,
                    'dataPoints': [{'timeUnixNano': now_nanos, 'asInt': int(value)}],
                },
            })
    return metrics_payload
