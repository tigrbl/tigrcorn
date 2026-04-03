import io
import logging

from tigrcorn.observability.events import Event
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.observability.metrics import Metrics
from tigrcorn.observability.tracing import span
from tigrcorn.workers.local import LocalWorker
from tigrcorn.workers.supervisor import WorkerSupervisor


import pytest

def test_logging_metrics_workers():
    logger = configure_logging('info')
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        access = AccessLogger(logger, enabled=True)
        access.log_http(('127.0.0.1', 1), 'GET', '/', 200, 'HTTP/1.1')
        access.log_ws(('127.0.0.1', 1), '/ws', 'accepted')
    finally:
        logger.removeHandler(handler)
    data = stream.getvalue()
    assert 'GET / HTTP/1.1' in data
    assert 'WEBSOCKET /ws' in data
    metrics = Metrics(connections_opened=1, requests_served=2)
    assert metrics.requests_served == 2
    event = Event(name='tick', attrs={'value': 1})
    assert event.attrs['value'] == 1
    with span('demo'):
        pass
    worker = LocalWorker()
    sup = WorkerSupervisor()
    sup.add(worker)
    sup.start_all()
    assert worker.running
    sup.stop_all()
    assert not (worker.running)