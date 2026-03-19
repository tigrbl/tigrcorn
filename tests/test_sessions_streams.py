import unittest

from tigrcorn.sessions.connection import ConnectionSession
from tigrcorn.sessions.manager import SessionManager
from tigrcorn.sessions.quic import QuicSession
from tigrcorn.streams.base import LogicalStream
from tigrcorn.streams.multiplex import MultiplexStream
from tigrcorn.streams.registry import StreamRegistry
from tigrcorn.streams.singleplex import SingleplexStream


class SessionsStreamsTests(unittest.TestCase):
    def test_session_manager(self):
        manager = SessionManager()
        session = manager.open(ConnectionSession(session_id=1, peer=('127.0.0.1', 1)))
        self.assertEqual(manager.snapshot()['tcp'], 1)
        manager.close(session.session_id)
        self.assertEqual(manager.snapshot()['tcp'], 0)

    def test_quic_session(self):
        session = QuicSession(session_id=5)
        session.opened_stream()
        session.opened_stream()
        self.assertEqual(session.stream_count, 2)

    def test_stream_registry(self):
        registry = StreamRegistry()
        stream = registry.add(LogicalStream(stream_id=1))
        self.assertIs(registry.get(1), stream)
        registry.close(1)
        self.assertIsNone(registry.get(1))

    def test_stream_types(self):
        self.assertFalse(SingleplexStream().multiplexed)
        self.assertTrue(MultiplexStream(3).multiplexed)
