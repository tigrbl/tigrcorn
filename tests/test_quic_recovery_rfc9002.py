import unittest

from tigrcorn.transports.quic.recovery import QuicLossRecovery


class QuicRecoveryRFC9002Tests(unittest.TestCase):
    def test_rtt_and_pto_are_maintained(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.on_packet_sent(1, 1200, sent_time=1.0)
        recovery.on_ack_received([1], now=1.1)
        self.assertGreater(recovery.rtt.smoothed_rtt, 0)
        self.assertGreater(recovery.pto_timeout(), recovery.rtt.smoothed_rtt)
        self.assertEqual(recovery.pto_count, 0)

    def test_loss_detection_and_cwnd_reduction(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        for pn, sent in [(1, 1.0), (2, 1.01), (3, 1.02), (4, 1.03), (5, 1.04)]:
            recovery.on_packet_sent(pn, 1200, sent_time=sent)
        initial_cwnd = recovery.congestion_window
        recovery.on_ack_received([5], now=1.20)
        recovery.on_ack_received([5], now=1.20)
        self.assertNotIn(1, recovery.outstanding)
        self.assertLessEqual(recovery.congestion_window, initial_cwnd)

    def test_pto_backoff_increments(self):
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.on_packet_sent(1, 1200, sent_time=1.0)
        first = recovery.next_pto_deadline(now=1.0)
        recovery.on_pto_expired()
        second = recovery.next_pto_deadline(now=1.0)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertGreater(second, first)
