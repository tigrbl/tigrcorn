import asyncio
from dataclasses import asdict
import subprocess
import sys

import pytest

from tigrcorn_config.model import AdmissionConfig, ServerConfig
from tigrcorn_config.defaults import default_config
from tigrcorn_config.model.admission import ADMISSION_FIELDS
from tigrcorn_config.load import (
    build_config_from_sources,
    build_config_from_namespace,
    config_from_mapping,
)
from tigrcorn_runtime.cli import build_parser
from tigrcorn_protocols.scheduler.admission import AdmissionController, AdmissionDenied


def test_all_fields_have_cli_toml_environment_and_python_parity(tmp_path, monkeypatch):
    values = {name: 2.5 if "_rate_" in name else 4 for name in ADMISSION_FIELDS}
    typed = AdmissionConfig(**values)
    path = tmp_path / "server.toml"
    path.write_text(
        "[admission]\n" + "\n".join(f"{k}={v}" for k, v in values.items()),
        encoding="utf-8",
    )
    file = build_config_from_sources(config_path=path)
    assert asdict(file.admission) == asdict(typed)
    for k, v in values.items():
        monkeypatch.setenv("TIGRCORN_" + k.upper(), str(v))
    env = build_config_from_sources()
    assert asdict(env.admission) == asdict(typed)
    args = ["app:app"]
    for k, v in values.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    cli = build_config_from_namespace(build_parser().parse_args(args))
    assert asdict(cli.admission) == asdict(typed)
    monkeypatch.setenv("TIGRCORN_MAX_ACTIVE_STREAMS_PER_SOURCE", "7")
    resolved = build_config_from_sources(
        config_path=path,
        cli_overrides={"admission": {"max_active_streams_per_source": 3}},
    )
    assert resolved.admission.max_active_streams_per_source == 3


@pytest.mark.parametrize(
    "block",
    [
        {"max_active_streams_per_source": 0},
        {"max_connections_per_instance": True},
        {"max_active_streams_per_connection": 1.5},
        {"unknown": 2},
        {
            "stream_open_rate_per_source": float("nan"),
            "stream_open_burst_per_source": 2,
        },
        {
            "stream_open_rate_per_source": float("inf"),
            "stream_open_burst_per_source": 2,
        },
        {"stream_open_burst_per_source": 2},
    ],
)
def test_strict_admission_validation(block):
    with pytest.raises(ValueError):
        config_from_mapping({"admission": block})


def test_connection_and_source_caps_span_controllers_and_ports(tmp_path):
    policy = AdmissionConfig(
        max_connections_per_source=1,
        max_active_streams_per_instance=2,
        max_active_streams_per_source=1,
    )
    a = AdmissionController(policy, path=str(tmp_path / "instance.db"))
    b = AdmissionController(policy, path=a.path)
    connection = a.acquire("connection", source=("127.0.0.1", 100), connection_id="a")
    with pytest.raises(AdmissionDenied):
        b.acquire("connection", source=("127.0.0.1", 200), connection_id="b")
    stream = a.acquire("stream", source=("127.0.0.1", 100), connection_id="a")
    with pytest.raises(AdmissionDenied) as exc:
        b.acquire("stream", source=("127.0.0.1", 200), connection_id="b")
    assert exc.value.scope == "source"
    other = b.acquire("stream", source=("127.0.0.2", 200), connection_id="b")
    with pytest.raises(AdmissionDenied) as exc:
        b.acquire("stream", source=("127.0.0.3", 200), connection_id="c")
    assert exc.value.scope == "instance"
    stream.release()
    stream.release()
    other.release()
    connection.release()
    assert not a.snapshot()["active"]
    a.close()
    b.close()


def test_reset_and_capacity_failure_do_not_refund_tokens(tmp_path):
    now = [100.0]
    a = AdmissionController(
        AdmissionConfig(
            max_active_streams_per_source=1,
            stream_open_rate_per_source=1,
            stream_open_burst_per_source=2,
        ),
        path=str(tmp_path / "rates.db"),
        clock=lambda: now[0],
    )
    first = a.acquire("stream", source="source", connection_id="1")
    with pytest.raises(AdmissionDenied) as exc:
        a.acquire("stream", source="source", connection_id="2")
    assert exc.value.reason == "capacity"
    first.release()
    with pytest.raises(AdmissionDenied) as exc:
        a.acquire("stream", source="source", connection_id="3")
    assert exc.value.reason == "rate"
    now[0] += 1
    a.acquire("stream", source="source", connection_id="4").release()
    a.close()


def test_session_attachment_does_not_double_charge_global_streams(tmp_path):
    a = AdmissionController(
        AdmissionConfig(
            max_active_streams_per_instance=2, max_active_streams_per_session=1
        ),
        path=str(tmp_path / "session.db"),
    )
    first = a.acquire("stream", source="source", connection_id="1")
    a.attach_session(first.id, "session")
    second = a.acquire("stream", source="source", connection_id="1")
    with pytest.raises(AdmissionDenied):
        a.attach_session(second.id, "session")
    assert a.snapshot()["active"]["stream"] == 2
    first.release()
    a.attach_session(second.id, "session")
    second.release()
    a.close()


def test_worker_crash_reclaims_only_confirmed_dead_owner(tmp_path):
    path = str(tmp_path / "workers.db")
    a = AdmissionController(
        AdmissionConfig(max_active_streams_per_instance=1), path=path
    )
    script = """import os,sys
from tigrcorn_config.model import AdmissionConfig
from tigrcorn_protocols.scheduler.admission import AdmissionController
a=AdmissionController(AdmissionConfig(max_active_streams_per_instance=1),path=sys.argv[1],owner='test-worker-generation')
a.acquire('stream',source='source',connection_id='worker')
os._exit(0)
"""
    child = subprocess.Popen([sys.executable, "-c", script, path])
    assert child.wait(timeout=10) == 0
    with pytest.raises(AdmissionDenied):
        a.acquire("stream", source="other", connection_id="other")
    a.reclaim_owner("test-worker-generation")
    a.acquire("stream", source="other", connection_id="other").release()
    a.close()


def test_h2_refusal_emits_reset_and_does_not_dispatch_application(tmp_path):
    asyncio.run(_h2_refusal(tmp_path))


async def _h2_refusal(tmp_path):
    from tigrcorn_protocols.http2.handler import HTTP2ConnectionHandler
    from tigrcorn_protocols.http2.codec import (
        HTTP2Frame,
        FRAME_HEADERS,
        FLAG_END_HEADERS,
        FLAG_END_STREAM,
        FrameBuffer,
        FRAME_RST_STREAM,
    )
    from tigrcorn_protocols.http2.hpack import encode_header_block
    from tigrcorn_observability.logging import AccessLogger, configure_logging
    from tigrcorn_protocols.scheduler.runtime import ProductionScheduler

    class Writer:
        def __init__(self):
            self.writes = []

        def write(self, data):
            self.writes.append(data)

        async def drain(self):
            pass

    called = []
    block = asyncio.Event()

    async def app(scope, receive, send):
        called.append(scope["path"])
        await block.wait()

    scheduler = ProductionScheduler()
    scheduler.admission = AdmissionController(
        AdmissionConfig(max_active_streams_per_source=1), path=str(tmp_path / "h2.db")
    )
    handlers = []
    for n in range(2):
        handlers.append(
            HTTP2ConnectionHandler(
                app=app,
                config=default_config(),
                access_logger=AccessLogger(configure_logging("warning"), enabled=False),
                scheduler=scheduler,
                reader=None,
                writer=Writer(),
                client=("127.0.0.1", 100 + n),
                server=None,
                scheme="http",
                connection_id=str(n),
            )
        )
    payload = encode_header_block(
        [
            (b":method", b"GET"),
            (b":path", b"/watch"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
        ]
    )
    frame = HTTP2Frame(
        frame_type=FRAME_HEADERS,
        flags=FLAG_END_HEADERS | FLAG_END_STREAM,
        stream_id=1,
        payload=payload,
    )
    try:
        await handlers[0]._handle_headers(frame)
        await asyncio.sleep(0)
        await handlers[1]._handle_headers(frame)
        await asyncio.sleep(0)
        assert called == ["/watch"]
        buffer = FrameBuffer()
        buffer.feed(b"".join(handlers[1].writer.writes))
        frames = buffer.pop_all()
        assert any(f.frame_type == FRAME_RST_STREAM for f in frames)
        assert scheduler.admission.snapshot()["active"]["stream"] == 1
    finally:
        for handler in handlers:
            await handler._shutdown_streams()
        scheduler.admission.close()


def test_h3_half_close_and_control_reservations(tmp_path):
    from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler
    from tigrcorn_protocols.http3.handler.session import HTTP3Session
    from tigrcorn_transports.quic.connection import QuicConnection
    from tigrcorn_transports.quic.streams.frames import QuicStreamFrame
    from tigrcorn_protocols.scheduler.runtime import ProductionScheduler
    from tigrcorn_config.model import ListenerConfig

    scheduler = ProductionScheduler()
    scheduler.admission = AdmissionController(
        AdmissionConfig(max_active_streams_per_connection=1),
        path=str(tmp_path / "h3.db"),
    )
    handler = HTTP3DatagramHandler(
        app=None,
        config=ServerConfig(),
        listener=ListenerConfig(),
        access_logger=None,
        scheduler=scheduler,
    )
    session = HTTP3Session(addr=("127.0.0.1", 10), quic=QuicConnection(is_client=False))
    assert handler._assign_session_runtime_id(session)
    handler._admit_h3_stream(session, 2, b"\x00")
    assert session.admission_controls == {2}
    handler._admit_h3_stream(session, 0, b"data")
    state = session.quic.streams.get(0)
    state.apply(QuicStreamFrame(stream_id=0, offset=0, data=b"", fin=True))
    handler._reap_admission_streams(session)
    assert len(session.admission_streams) == 1
    with pytest.raises(AdmissionDenied):
        handler._admit_h3_stream(session, 4, b"data")
    state.reserve_send(b"", fin=True)
    handler._reap_admission_streams(session)
    assert not session.admission_streams
    handler._admit_h3_stream(session, 4, b"data")
    handler._release_h3_admission(session)
    assert not scheduler.admission.snapshot()["active"]
    scheduler.admission.close()


def test_real_workers_share_connection_budget_and_recover_after_death(tmp_path):
    import socket
    import time
    from tigrcorn_runtime.server.supervisor import ServerSupervisor

    app_path = tmp_path / "admission_worker_app.py"
    app_path.write_text(
        """import asyncio
async def app(scope,receive,send):
    await receive()
    await send({'type':'http.response.start','status':200,'headers':[]})
    await send({'type':'http.response.body','body':b'open','more_body':False})
""",
        encoding="utf-8",
    )
    cfg = config_from_mapping(
        {
            "app": {
                "target": "admission_worker_app:app",
                "app_dir": str(tmp_path),
                "lifespan": "off",
            },
            "listeners": [{"host": "127.0.0.1", "port": 0}],
            "process": {"workers": 2, "runtime": "asyncio"},
            "admission": {"max_connections_per_instance": 1},
        }
    )
    supervisor = ServerSupervisor(app_target=cfg.app.target, config=cfg)
    connections = []
    try:
        supervisor.start()
        deadline = time.monotonic() + 15
        while not all(worker.ready for worker in supervisor.workers.workers):
            supervisor.poll_workers_once()
            if time.monotonic() > deadline:
                raise AssertionError("workers did not become ready")
            time.sleep(0.01)
        port = supervisor.bound_sockets[0].getsockname()[1]
        first = socket.create_connection(("127.0.0.1", port), timeout=3)
        connections.append(first)
        first.sendall(b"GET / HTTP/1.1\r\nHost: example\r\n\r\n")
        assert b"200" in first.recv(4096)
        denied = socket.create_connection(("127.0.0.1", port), timeout=3)
        connections.append(denied)
        denied.sendall(b"GET / HTTP/1.1\r\nHost: example\r\n\r\n")
        try:
            assert denied.recv(4096) == b""
        except (ConnectionResetError, ConnectionAbortedError):
            pass
        rows = supervisor._admission_coordinator.db.execute(
            "SELECT owner FROM leases WHERE kind='connection'"
        ).fetchall()
        assert len(rows) == 1
        owner = rows[0][0]
        worker = next(
            w for w in supervisor.workers.workers if w.admission_owner == owner
        )
        worker.stop(timeout=1)
        assert supervisor.poll_workers_once()
        assert (
            supervisor._admission_coordinator.snapshot()["active"].get("connection", 0)
            == 0
        )
        fresh = socket.create_connection(("127.0.0.1", port), timeout=3)
        connections.append(fresh)
        fresh.sendall(b"GET / HTTP/1.1\r\nHost: example\r\n\r\n")
        assert b"200" in fresh.recv(4096)
    finally:
        for conn in connections:
            conn.close()
        supervisor.stop()


def test_tracking_budget_covers_pending_and_session_buckets(tmp_path):
    now = [100.0]
    capped = AdmissionController(
        AdmissionConfig(
            max_tracking_entries=1,
            stream_open_rate_per_connection=1,
            stream_open_burst_per_connection=1,
            stream_open_rate_per_source=1,
            stream_open_burst_per_source=1,
        ),
        path=str(tmp_path / "pending.db"),
        clock=lambda: now[0],
    )
    with pytest.raises(AdmissionDenied) as exc:
        capped.acquire("stream", source="source", connection_id="one")
    assert exc.value.reason == "tracking_capacity"
    assert capped.db.execute("SELECT count(*) FROM buckets").fetchone()[0] == 0
    capped.close()
    sessions = AdmissionController(
        AdmissionConfig(
            max_tracking_entries=1,
            stream_open_rate_per_session=1,
            stream_open_burst_per_session=1,
        ),
        path=str(tmp_path / "attached.db"),
        clock=lambda: now[0],
    )
    first = sessions.acquire("stream", source="source", connection_id="one")
    sessions.attach_session(first.id, "session-one")
    first.release()
    second = sessions.acquire("stream", source="source", connection_id="one")
    with pytest.raises(AdmissionDenied) as exc:
        sessions.attach_session(second.id, "session-two")
    assert exc.value.reason == "tracking_capacity"
    now[0] += 2
    sessions.attach_session(second.id, "session-two")
    assert sessions.db.execute("SELECT count(*) FROM buckets").fetchone()[0] == 1
    second.release()
    sessions.close()
