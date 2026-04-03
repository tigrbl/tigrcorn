from tigrcorn.sessions.connection import ConnectionSession
from tigrcorn.sessions.manager import SessionManager
from tigrcorn.sessions.quic import QuicSession
from tigrcorn.streams.base import LogicalStream
from tigrcorn.streams.multiplex import MultiplexStream
from tigrcorn.streams.registry import StreamRegistry
from tigrcorn.streams.singleplex import SingleplexStream


def test_session_manager() -> None:
    manager = SessionManager()
    session = manager.open(ConnectionSession(session_id=1, peer=("127.0.0.1", 1)))
    assert manager.snapshot()["tcp"] == 1
    manager.close(session.session_id)
    assert manager.snapshot()["tcp"] == 0


def test_quic_session() -> None:
    session = QuicSession(session_id=5)
    session.opened_stream()
    session.opened_stream()
    assert session.stream_count == 2


def test_stream_registry() -> None:
    registry = StreamRegistry()
    stream = registry.add(LogicalStream(stream_id=1))
    assert registry.get(1) is stream
    registry.close(1)
    assert registry.get(1) is None


def test_stream_types() -> None:
    assert not SingleplexStream().multiplexed
    assert MultiplexStream(3).multiplexed
