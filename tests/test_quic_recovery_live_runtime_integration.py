import time
import unittest

from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler, HTTP3Session
from tigrcorn.transports.quic import QuicConnection, decode_packet
from tigrcorn.transports.quic.connection import PACKET_SPACE_APPLICATION
from tigrcorn.transports.quic.packets import QuicShortHeaderPacket


class QuicRecoveryLiveRuntimeIntegrationTests(unittest.TestCase):
    def _pair(self) -> tuple[QuicConnection, QuicConnection]:
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        return client, server

    def test_ack_driven_loss_detection_queues_retransmission(self):
        client, server = self._pair()
        packets = [client.send_stream_data(0, chunk, fin=False) for chunk in (b'a', b'b', b'c', b'd')]
        server.receive_datagram(packets[2])
        server.receive_datagram(packets[3])
        acknowledgements = server.take_pending_datagrams()
        self.assertEqual(len(acknowledgements), 1)
        client.receive_datagram(acknowledgements[0])
        retransmissions = client.take_pending_datagrams()
        self.assertTrue(retransmissions)
        retransmit_packet = decode_packet(retransmissions[0], destination_connection_id_length=len(server.local_cid))
        self.assertIsInstance(retransmit_packet, QuicShortHeaderPacket)
        events = []
        for datagram in retransmissions:
            events.extend(server.receive_datagram(datagram))
        self.assertTrue(any(event.kind == 'stream' and event.stream_id == 0 and event.data == b'a' for event in events))

    def test_pto_expiry_generates_probe_packets(self):
        client, _server = self._pair()
        client.send_stream_data(0, b'probe-me', fin=False)
        outstanding = client.recovery.spaces[PACKET_SPACE_APPLICATION].outstanding[0]
        outstanding.sent_time = time.monotonic() - 2.0
        client._update_runtime_timers(now=time.monotonic())
        probes = client.drain_scheduled_datagrams()
        self.assertTrue(probes)
        self.assertGreater(client.recovery.pto_count, 0)

    def test_recovery_state_is_tracked_per_path_after_rebinding(self):
        stationary = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        mover = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
        stationary.receive_datagram(mover.send_stream_data(0, b'first', fin=False), addr=('127.0.0.1', 1000))
        first_path = stationary.recovery
        stationary.receive_datagram(mover.send_stream_data(4, b'second', fin=False), addr=('127.0.0.1', 1001))
        second_path = stationary.recovery
        self.assertIsNot(first_path, second_path)
        self.assertIn(('127.0.0.1', 1000), stationary._path_states)
        self.assertIn(('127.0.0.1', 1001), stationary._path_states)


class HTTP3RecoveryRuntimeSendPathTests(unittest.TestCase):
    def test_handler_defers_and_flushes_recovery_blocked_datagrams(self):
        async def app(scope, receive, send):
            raise AssertionError('app should not be invoked')

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3'], quic_secret=b'shared'),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )

        class Endpoint:
            def __init__(self):
                self.sent = []
                self.local_addr = ('127.0.0.1', 4433)

            def send(self, data, addr):
                self.sent.append((data, addr))

        endpoint = Endpoint()
        session = HTTP3Session(
            addr=('127.0.0.1', 50000),
            quic=QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1'),
            address_validated=True,
        )
        session.quic.address_validated = True
        raw = session.quic.send_stream_data(1, b'response', fin=True)
        session.quic.recovery.congestion_window = 0
        handler._queue_or_send(session, raw, endpoint, session.addr)
        self.assertEqual(endpoint.sent, [])
        self.assertEqual(len(session.pending_outbound), 1)
        session.quic.recovery.congestion_window = 64_000
        session.quic.recovery.pacing_budget = 64_000
        handler._flush_pending_outbound(session, endpoint)
        self.assertEqual(len(endpoint.sent), 1)
        self.assertEqual(session.pending_outbound, [])


if __name__ == '__main__':
    unittest.main()
