import unittest

from tigrcorn.listeners.registry import LISTENER_TYPES
from tigrcorn.protocols.custom.registry import CustomProtocolRegistry
from tigrcorn.protocols.registry import BUILTIN_PROTOCOLS
from tigrcorn.sessions.limits import SessionLimits
from tigrcorn.sessions.metadata import SessionMetadata
from tigrcorn.transports.base import TransportDescriptor
from tigrcorn.transports.registry import TRANSPORTS
from tigrcorn.workers.model import WorkerConfig


class RegistriesModelsTests(unittest.TestCase):
    def test_listener_and_transport_registries(self):
        self.assertIn('udp', LISTENER_TYPES)
        self.assertTrue(TRANSPORTS['quic'].multiplexed)
        desc = TransportDescriptor(name='x', multiplexed=True)
        self.assertTrue(desc.multiplexed)

    def test_protocol_registry(self):
        self.assertIn('http3', BUILTIN_PROTOCOLS)
        self.assertEqual(BUILTIN_PROTOCOLS['http3'].asgi_scope_types, ('http',))
        registry = CustomProtocolRegistry()
        registry.register('demo', lambda: 'ok')
        self.assertEqual(registry.get('demo')(), 'ok')

    def test_session_and_worker_models(self):
        limits = SessionLimits(max_streams=2)
        self.assertTrue(limits.allow_stream(1))
        self.assertFalse(limits.allow_stream(2))
        metadata = SessionMetadata(listener_name='pub', transport='udp', label='udp://127.0.0.1:1')
        self.assertEqual(metadata.transport, 'udp')
        worker = WorkerConfig(processes=2, graceful_shutdown_timeout=5)
        self.assertEqual(worker.processes, 2)
