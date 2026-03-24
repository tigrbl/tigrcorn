
from __future__ import annotations

import tempfile
from pathlib import Path

from benchmarks.common import measure_sync
from tigrcorn.asgi.scopes.http import build_http_scope
from tigrcorn.config.model import AppConfig, ProxyConfig, ServerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.observability.metrics import Metrics
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.server.reloader import PollingReloader
from tigrcorn.workers.local import LocalWorker
from tigrcorn.workers.supervisor import WorkerSupervisor

_REQUEST = ParsedRequest(
    method='GET',
    target='/svc/hello',
    path='/svc/hello',
    raw_path=b'/svc/hello',
    query_string=b'',
    http_version='1.1',
    headers=[
        (b'x-forwarded-for', b'203.0.113.8'),
        (b'x-forwarded-proto', b'https'),
        (b'x-forwarded-host', b'example.com'),
        (b'x-forwarded-prefix', b'/svc'),
    ],
    body=b'',
    keep_alive=True,
    expect_continue=False,
    websocket_upgrade=False,
)


def logging_off_driver(profile, *, source_root):
    logger = configure_logging('info')
    access = AccessLogger(logger, enabled=False)
    def operation():
        access.log_http(('127.0.0.1', 1), 'GET', '/', 200, 'HTTP/1.1')
        return {'correctness': {'logging_disabled_no_error': True}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)


def logging_on_driver(profile, *, source_root):
    tempdir = tempfile.TemporaryDirectory()
    class Config:
        level = 'info'
        structured = True
        access_log_file = str(Path(tempdir.name) / 'access.log')
        error_log_file = str(Path(tempdir.name) / 'error.log')
    logger = configure_logging('info', config=Config())
    access = AccessLogger(logger, enabled=True)
    def operation():
        access.log_http(('127.0.0.1', 1), 'GET', '/', 200, 'HTTP/1.1')
        for handler in logger.handlers:
            handler.flush()
        return {'correctness': {'access_log_file_exists': Path(Config.access_log_file).exists()}}
    measurement = measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)
    tempdir.cleanup()
    return measurement


def metrics_off_driver(profile, *, source_root):
    def operation():
        return {'correctness': {'metrics_disabled_noop': True}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)


def metrics_on_driver(profile, *, source_root):
    metrics = Metrics()
    def operation():
        metrics.connection_opened()
        metrics.requests_served += 1
        metrics.websocket_opened()
        prom = metrics.render_prometheus()
        statsd = metrics.render_statsd()
        return {
            'connections': 1,
            'correctness': {
                'prometheus_emitted': 'tigrcorn_requests_served' in prom,
                'statsd_emitted': 'tigrcorn.requests_served' in statsd,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)


def proxy_headers_off_driver(profile, *, source_root):
    def operation():
        scope = build_http_scope(_REQUEST, client=('127.0.0.1', 50000), server=('127.0.0.1', 8000), scheme='http', root_path='')
        return {'connections': 1, 'correctness': {'root_path_empty': scope['root_path'] == '', 'path_unchanged': scope['path'] == '/svc/hello'}}
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)


def proxy_headers_on_driver(profile, *, source_root):
    proxy = ProxyConfig(proxy_headers=True, forwarded_allow_ips=['127.0.0.1'])
    def operation():
        scope = build_http_scope(_REQUEST, client=('127.0.0.1', 50000), server=('127.0.0.1', 8000), scheme='http', root_path='', proxy=proxy)
        return {
            'connections': 1,
            'correctness': {
                'proxy_applied': scope['scheme'] == 'https' and scope['root_path'] == '/svc' and scope['path'] == '/hello',
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)


def worker_scaleout_driver(profile, *, source_root):
    worker_count = int(profile.driver_config.get('workers', 4))
    def operation():
        supervisor = WorkerSupervisor(auto_restart=True)
        for index in range(worker_count):
            supervisor.add(LocalWorker(name=f'w{index}'))
        supervisor.start_all()
        snapshot = supervisor.snapshot()
        supervisor.replace(0)
        supervisor.stop_all()
        return {
            'connections': worker_count,
            'correctness': {
                'all_workers_started': all(item['alive'] for item in snapshot),
                'replace_kept_worker': len(supervisor.workers) == worker_count,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=worker_count)


def graceful_drain_driver(profile, *, source_root):
    worker_count = int(profile.driver_config.get('workers', 4))
    def operation():
        supervisor = WorkerSupervisor(auto_restart=False)
        workers = [LocalWorker(name=f'drain-{index}') for index in range(worker_count)]
        for worker in workers:
            supervisor.add(worker)
        supervisor.start_all()
        supervisor.stop_all()
        return {
            'connections': worker_count,
            'correctness': {
                'all_workers_stopped': all(not worker.running for worker in workers),
                'stop_counts_recorded': all(worker.stop_count >= 1 for worker in workers),
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=worker_count)


def reload_overhead_driver(profile, *, source_root):
    tempdir = tempfile.TemporaryDirectory()
    reload_root = Path(tempdir.name)
    target = reload_root / 'app.py'
    target.write_text('value = 1\n', encoding='utf-8')
    config = ServerConfig(app=AppConfig(target='tests.fixtures_pkg.appmod:app', reload_dirs=[str(reload_root)], reload_include=['*.py']))
    reloader = PollingReloader(['tests.fixtures_pkg.appmod:app'], config=config)
    counter = {'value': 1}
    def operation():
        before = reloader.snapshot()
        counter['value'] += 1
        target.write_text(f'value = {counter["value"]}\n', encoding='utf-8')
        after = reloader.snapshot()
        return {'correctness': {'reload_detects_change': before != after}}
    measurement = measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups)
    tempdir.cleanup()
    return measurement
