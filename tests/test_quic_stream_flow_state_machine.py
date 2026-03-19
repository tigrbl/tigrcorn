import time
import unittest

from tigrcorn.errors import ProtocolError
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.connection import PACKET_SPACE_APPLICATION
from tigrcorn.transports.quic.handshake import TransportParameters
from tigrcorn.transports.quic.streams import QuicResetStreamFrame


class QuicStreamFlowStateMachineTests(unittest.TestCase):
    def _pair(self) -> tuple[QuicConnection, QuicConnection]:
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1cli1', remote_cid=b'srv1srv1')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        return client, server

    def test_peer_initiated_stream_limit_is_enforced(self):
        client, server = self._pair()
        server.streams.configure_local_initial_limits(bidirectional=1, unidirectional=0)
        server.receive_datagram(client.send_stream_data(0, b'a', fin=True))
        with self.assertRaises(ProtocolError):
            server.receive_datagram(client.send_stream_data(4, b'b', fin=True))

    def test_unidirectional_stream_role_is_enforced(self):
        client, server = self._pair()
        server.receive_datagram(client.send_stream_data(2, b'hello', fin=True))
        with self.assertRaises(ProtocolError):
            server.send_stream_data(2, b'reply')

    def test_distinct_bidi_local_bidi_remote_and_uni_send_windows_are_applied(self):
        # peer-initiated bidirectional stream uses peer bidi_local credit
        client, server = self._pair()
        server.streams.configure_peer_initial_limits(bidirectional=10, unidirectional=10)
        server.flow.configure_peer_initial_limits(
            max_data=128,
            max_stream_data_bidi_local=3,
            max_stream_data_bidi_remote=7,
            max_stream_data_uni=11,
        )
        server.receive_datagram(client.send_stream_data(0, b'x', fin=False))
        with self.assertRaises(ProtocolError):
            server.send_stream_data(0, b'abcd')
        self.assertIsInstance(server.send_stream_data(0, b'abc'), bytes)

        # local-initiated bidirectional stream uses peer bidi_remote credit
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        server.streams.configure_peer_initial_limits(bidirectional=10, unidirectional=10)
        server.flow.configure_peer_initial_limits(
            max_data=128,
            max_stream_data_bidi_local=3,
            max_stream_data_bidi_remote=7,
            max_stream_data_uni=11,
        )
        with self.assertRaises(ProtocolError):
            server.send_stream_data(1, b'abcdefgh')
        self.assertIsInstance(server.send_stream_data(1, b'abcdefg'), bytes)

        # local-initiated unidirectional stream uses peer uni credit
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b'srv1srv1', remote_cid=b'cli1cli1')
        server.streams.configure_peer_initial_limits(bidirectional=10, unidirectional=10)
        server.flow.configure_peer_initial_limits(
            max_data=128,
            max_stream_data_bidi_local=3,
            max_stream_data_bidi_remote=7,
            max_stream_data_uni=11,
        )
        with self.assertRaises(ProtocolError):
            server.send_stream_data(3, b'abcdefghijkl')
        self.assertIsInstance(server.send_stream_data(3, b'abcdefghijk'), bytes)

    def test_receive_side_flow_control_rejects_stream_data_beyond_local_limits(self):
        client, server = self._pair()
        server.flow.configure_local_initial_limits(
            max_data=4,
            max_stream_data_bidi_local=4,
            max_stream_data_bidi_remote=4,
            max_stream_data_uni=4,
        )
        with self.assertRaises(ProtocolError):
            server.receive_datagram(client.send_stream_data(0, b'abcde', fin=False))

    def test_reset_stream_final_size_counts_toward_receive_flow_control(self):
        client, server = self._pair()
        server.flow.configure_local_initial_limits(
            max_data=4,
            max_stream_data_bidi_local=10,
            max_stream_data_bidi_remote=10,
            max_stream_data_uni=10,
        )
        server.receive_datagram(client.send_stream_data(0, b'abc', fin=False))
        oversized_reset = client.send_frames(
            [QuicResetStreamFrame(stream_id=0, error_code=1, final_size=5)],
            packet_space=PACKET_SPACE_APPLICATION,
        )
        with self.assertRaises(ProtocolError):
            server.receive_datagram(oversized_reset)

    def test_stop_sending_queues_reset_stream(self):
        client, server = self._pair()
        server.receive_datagram(client.send_stream_data(0, b'abc', fin=False))
        stop_events = client.receive_datagram(server.stop_sending(0, 99))
        self.assertTrue(any(event.kind == 'stop_sending' and event.stream_id == 0 for event in stop_events))
        pending = client.take_pending_datagrams()
        self.assertEqual(len(pending), 1)
        reset_events = server.receive_datagram(pending[0])
        self.assertTrue(any(event.kind == 'reset_stream' and event.stream_id == 0 for event in reset_events))

    def test_closed_peer_stream_recycles_max_streams_credit(self):
        client, server = self._pair()
        server.streams.configure_local_initial_limits(bidirectional=1, unidirectional=0)
        server.receive_datagram(client.send_stream_data(0, b'request', fin=True))
        server.send_stream_data(0, b'response', fin=True)
        pending = server.take_pending_datagrams()
        self.assertEqual(len(pending), 1)
        events = client.receive_datagram(pending[0])
        max_stream_events = [event for event in events if event.kind == 'max_streams']
        self.assertEqual(len(max_stream_events), 1)
        self.assertTrue(max_stream_events[0].detail.bidirectional)
        self.assertEqual(max_stream_events[0].detail.maximum_streams, 2)

    def test_ack_delay_exponent_is_used_when_encoding_ack_frames(self):
        _client, server = self._pair()
        server.local_transport_parameters = TransportParameters(ack_delay_exponent=4)
        server._mark_received(PACKET_SPACE_APPLICATION, 7)
        server._space_state(PACKET_SPACE_APPLICATION).received_packet_times[7] = time.monotonic() - 0.032
        ack = server._build_ack_frame(PACKET_SPACE_APPLICATION)
        self.assertGreaterEqual(ack.ack_delay, 1500)

    def test_credit_connection_and_stream_expand_local_receive_limits_only(self):
        _client, server = self._pair()
        send_limit = server.flow.connection_window
        local_limit = server.flow.local_connection_window
        server.credit_connection(10)
        self.assertEqual(server.flow.connection_window, send_limit)
        self.assertEqual(server.flow.local_connection_window, local_limit + 10)

        stream_send_limit = server.flow.window_for_stream(0)
        stream_recv_limit = server.flow.receive_window_for_stream(0)
        server.credit_stream(0, 5)
        self.assertEqual(server.flow.window_for_stream(0), stream_send_limit)
        self.assertEqual(server.flow.receive_window_for_stream(0), stream_recv_limit + 5)


if __name__ == '__main__':
    unittest.main()
