from __future__ import annotations

import time
from collections.abc import Mapping

from tigrcorn_quic_cc import (
    AckReceived,
    Clock,
    ControllerContext,
    ControllerSnapshot,
    EcnFeedback,
    MtuUpdated,
    PacketSent,
    PacketsLost,
    PersistentCongestion,
    SendLimits,
)

_GRANULARITY = 0.001


class RenoController:
    def __init__(
        self,
        context: ControllerContext,
        options: Mapping[str, object],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self.max_datagram_size = context.max_datagram_size
        self.minimum_congestion_window = 2 * context.max_datagram_size
        initial_packets = int(options.get("initial_window_packets", 10))
        initial_cap = int(options.get("initial_window_cap_bytes", 14_720))
        self.congestion_window = min(
            initial_packets * context.max_datagram_size,
            max(self.minimum_congestion_window, initial_cap),
        )
        self.ssthresh = 2**31 - 1
        self.congestion_recovery_start_time: float | None = None
        self.smoothed_rtt = 0.0
        self.latest_rtt = 0.0
        self.max_ack_delay = context.max_ack_delay
        self.persistent_congestion = False
        self._pacing_gain = float(options.get("pacing_gain", 1.0))

    def _pacing_rate(self) -> float:
        rtt = self.smoothed_rtt or self.latest_rtt or self.max_ack_delay or 0.333
        return max(
            float(self.max_datagram_size) / _GRANULARITY,
            (float(self.congestion_window) / max(rtt, _GRANULARITY))
            * self._pacing_gain,
        )

    def on_packet_sent(self, event: PacketSent) -> None:
        return None

    def on_ack_received(self, event: AckReceived) -> None:
        self.latest_rtt = event.latest_rtt
        self.smoothed_rtt = event.smoothed_rtt
        if event.bytes_acked <= 0:
            self.persistent_congestion = False
            return
        if self.congestion_window < self.ssthresh:
            self.congestion_window += event.bytes_acked
        else:
            increment = max(
                1,
                (self.max_datagram_size * event.bytes_acked)
                // max(self.congestion_window, 1),
            )
            self.congestion_window += increment
        self.persistent_congestion = False

    def on_packets_lost(self, event: PacketsLost) -> None:
        if not event.packets:
            return
        newest_lost_sent_time = max(packet.sent_time for packet in event.packets)
        if (
            self.congestion_recovery_start_time is None
            or newest_lost_sent_time > self.congestion_recovery_start_time
        ):
            self.congestion_recovery_start_time = event.now
            self.ssthresh = max(
                self.congestion_window // 2,
                self.minimum_congestion_window,
            )
            self.congestion_window = self.ssthresh

    def on_persistent_congestion(self, event: PersistentCongestion) -> None:
        self.congestion_window = self.minimum_congestion_window
        self.persistent_congestion = True

    def on_ecn_feedback(self, event: EcnFeedback) -> None:
        return None

    def on_mtu_updated(self, event: MtuUpdated) -> None:
        self.max_datagram_size = event.max_datagram_size
        self.minimum_congestion_window = 2 * event.max_datagram_size
        self.congestion_window = max(
            self.congestion_window,
            self.minimum_congestion_window,
        )

    def send_limits(self, now: float) -> SendLimits:
        return SendLimits(
            congestion_window=self.congestion_window,
            pacing_rate=self._pacing_rate(),
            send_quantum=self.max_datagram_size,
        )

    def snapshot(self) -> ControllerSnapshot:
        mode = "slow_start" if self.congestion_window < self.ssthresh else "avoidance"
        if self.persistent_congestion:
            mode = "persistent_congestion"
        return ControllerSnapshot(
            algorithm="reno",
            mode=mode,
            congestion_window=self.congestion_window,
            pacing_rate=self._pacing_rate(),
            send_quantum=self.max_datagram_size,
            measurements={
                "ssthresh": self.ssthresh,
                "recovery_start_time": self.congestion_recovery_start_time,
                "persistent_congestion": self.persistent_congestion,
            },
        )
