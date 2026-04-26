from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Iterator
from uuid import uuid4

from tigrcorn.observability.metrics import Metrics, OTEL_EXPORT_SCHEMA_VERSION, otel_metric_payload

_current_trace_id: ContextVar[str | None] = ContextVar('tigrcorn_trace_id', default=None)
_current_span_id: ContextVar[str | None] = ContextVar('tigrcorn_span_id', default=None)


@dataclass(slots=True)
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    start_time: float
    end_time: float | None = None
    attrs: dict[str, Any] | None = None


@contextmanager
def span(name: str, *, attrs: dict[str, Any] | None = None, sample_rate: float = 1.0, sink: callable | None = None) -> Iterator[SpanRecord | None]:
    if sample_rate <= 0 or random.random() > sample_rate:
        yield None
        return
    trace_id = _current_trace_id.get() or uuid4().hex
    span_id = uuid4().hex[:16]
    token_trace = _current_trace_id.set(trace_id)
    token_span = _current_span_id.set(span_id)
    record = SpanRecord(name=name, trace_id=trace_id, span_id=span_id, start_time=time.time(), attrs=dict(attrs or {}))
    try:
        yield record
    finally:
        record.end_time = time.time()
        if sink is not None:
            sink(record)
        _current_span_id.reset(token_span)
        _current_trace_id.reset(token_trace)


def parse_otel_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(str(endpoint).strip())
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('otel_endpoint must use http:// or https://')
    if not parsed.netloc:
        raise ValueError('otel_endpoint must include a network location')
    return urllib.parse.urlunparse(parsed)


class OtelExporter:
    def __init__(self, endpoint: str, *, service_name: str = 'tigrcorn', interval: float = 1.0, logger: logging.Logger | None = None, timeout: float = 2.0) -> None:
        self.endpoint = parse_otel_endpoint(endpoint)
        self.service_name = service_name
        self.interval = max(0.1, float(interval))
        self.logger = logger
        self.timeout = float(timeout)
        self._task: asyncio.Task[None] | None = None
        self._span_buffer: list[dict[str, Any]] = []
        self.buffer_limit = 256
        self.sent_batches = 0
        self.send_failures = 0
        self.last_error: str | None = None
        self.last_payload: dict[str, Any] | None = None

    def record_span(self, record: SpanRecord) -> None:
        payload = {
            'traceId': record.trace_id,
            'spanId': record.span_id,
            'name': record.name,
            'startTimeUnixNano': str(int(record.start_time * 1_000_000_000)),
            'endTimeUnixNano': str(int((record.end_time or record.start_time) * 1_000_000_000)),
            'attributes': [
                {
                    'key': key,
                    'value': {'stringValue': str(value)},
                }
                for key, value in sorted((record.attrs or {}).items())
            ],
        }
        self._span_buffer.append(payload)
        if len(self._span_buffer) > self.buffer_limit:
            self._span_buffer = self._span_buffer[-self.buffer_limit :]

    def _resource(self) -> dict[str, Any]:
        return {
            'attributes': [
                {'key': 'service.name', 'value': {'stringValue': self.service_name}},
            ]
        }

    def _build_payload(self, metrics: Metrics) -> dict[str, Any]:
        snapshot = metrics.snapshot()
        spans = list(self._span_buffer)
        return {
            'resourceMetrics': [
                {
                    'resource': self._resource(),
                    'scopeMetrics': [
                        {
                            'scope': {'name': 'tigrcorn', 'version': OTEL_EXPORT_SCHEMA_VERSION},
                            'metrics': otel_metric_payload(snapshot),
                        }
                    ],
                }
            ],
            'resourceSpans': [
                {
                    'resource': self._resource(),
                    'scopeSpans': [
                        {
                            'scope': {'name': 'tigrcorn', 'version': OTEL_EXPORT_SCHEMA_VERSION},
                            'spans': spans,
                        }
                    ],
                }
            ],
        }

    def _post_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode('utf-8')
        request = urllib.request.Request(self.endpoint, data=body, method='POST', headers={'content-type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            response.read()

    async def start(self, metrics: Metrics) -> None:
        if self._task is not None:
            return
        await self.export_now(metrics)
        self._task = asyncio.create_task(self._run(metrics), name='tigrcorn-otel-exporter')

    async def _run(self, metrics: Metrics) -> None:
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self.export_now(metrics)
        except asyncio.CancelledError:
            raise

    async def export_now(self, metrics: Metrics) -> None:
        payload = self._build_payload(metrics)
        self.last_payload = payload
        spans_before = list(self._span_buffer)
        try:
            await asyncio.to_thread(self._post_json, payload)
            self.sent_batches += 1
            self._span_buffer.clear()
        except Exception as exc:  # pragma: no cover - bounded failure path exercised in tests
            self.send_failures += 1
            self.last_error = str(exc)
            self._span_buffer = spans_before
            if self.logger is not None:
                self.logger.warning('otel exporter post failed: %s', exc)

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


def validate_otel_endpoint(endpoint: str | None) -> None:
    if endpoint:
        parse_otel_endpoint(endpoint)
