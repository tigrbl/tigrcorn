from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from tigrcorn_quic_cc import (
    AckReceived,
    CongestionControllerFactory,
    PacketSent,
    PacketsLost,
    PersistentCongestion,
)

from ..congestion import QuicCongestionRuntime
from .congestion import QuicRecoveryCongestionMixin
from .model import (
    _GRANULARITY,
    _PACKET_THRESHOLD,
    _PERSISTENT_CONGESTION_THRESHOLD,
    _TIME_THRESHOLD,
    LossSpace,
    PacketRecord,
    RecoverySnapshot,
    RttStats,
)


class QuicLossRecovery(QuicRecoveryCongestionMixin):
    def __init__(
        self,
        *,
        max_datagram_size: int = 1200,
        congestion_controller_factory: CongestionControllerFactory | None = None,
        congestion_controller_options: Mapping[str, object] | None = None,
        congestion_controller_options_validated: bool = False,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self.max_datagram_size = max_datagram_size
        self.congestion = QuicCongestionRuntime(
            max_datagram_size=max_datagram_size,
            factory=congestion_controller_factory,
            options=congestion_controller_options,
            options_validated=congestion_controller_options_validated,
            clock=self._clock,
        )
        self.bytes_in_flight = 0
        self.pto_count = 0
        self.rtt = RttStats()
        self.spaces: dict[str, LossSpace] = {
            'initial': LossSpace(name='initial'),
            'handshake': LossSpace(name='handshake'),
            'application': LossSpace(name='application'),
        }
        self.persistent_congestion = False
        self.persistent_congestion_total = 0

    @property
    def outstanding(self) -> dict[int, PacketRecord]:
        merged: dict[int, PacketRecord] = {}
        for space in self.spaces.values():
            merged.update(space.outstanding)
        return merged

    @property
    def largest_acked(self) -> int:
        return max(space.largest_acked for space in self.spaces.values())

    def now(self) -> float:
        return self._clock()

    def _space(self, packet_space: str) -> LossSpace:
        normalized = 'application' if packet_space == '0rtt' else packet_space
        if normalized not in self.spaces:
            self.spaces[normalized] = LossSpace(name=normalized)
        return self.spaces[normalized]

    def on_packet_sent(
        self,
        packet_number: int,
        bytes_sent: int,
        *,
        ack_eliciting: bool = True,
        packet_space: str = 'application',
        sent_time: float | None = None,
        is_pto_probe: bool = False,
        transmitted: bool = True,
    ) -> None:
        sent_at = self.now() if sent_time is None else sent_time
        space = self._space(packet_space)
        record = PacketRecord(
            packet_number=packet_number,
            sent_time=sent_at,
            bytes_sent=bytes_sent,
            ack_eliciting=ack_eliciting,
            in_flight=ack_eliciting and transmitted,
            packet_space=space.name,
            is_pto_probe=is_pto_probe,
        )
        space.outstanding[packet_number] = record
        space.largest_sent = max(space.largest_sent, packet_number)
        if ack_eliciting and transmitted:
            self.bytes_in_flight += bytes_sent
            self.spend_budget(bytes_sent, now=sent_at)
            self.congestion.on_packet_sent(
                PacketSent(
                    now=sent_at,
                    packet=self._packet_info(record),
                    bytes_in_flight=self.bytes_in_flight,
                )
            )
            record.controller_notified = True

    def deactivate_packet(
        self,
        packet_number: int,
        *,
        packet_space: str = 'application',
        now: float | None = None,
    ) -> bool:
        space = self._space(packet_space)
        record = space.outstanding.get(packet_number)
        if record is None or not record.in_flight:
            return False
        if record.ack_eliciting:
            self.bytes_in_flight = max(0, self.bytes_in_flight - record.bytes_sent)
            self.refund_budget(record.bytes_sent, now=now)
        record.in_flight = False
        return True

    def activate_packet(
        self,
        packet_number: int,
        *,
        packet_space: str = 'application',
        sent_time: float | None = None,
        now: float | None = None,
    ) -> bool:
        space = self._space(packet_space)
        record = space.outstanding.get(packet_number)
        if record is None:
            return False
        sent_at = self.now() if sent_time is None else sent_time
        record.sent_time = sent_at
        if record.in_flight or not record.ack_eliciting:
            return True
        record.in_flight = True
        self.bytes_in_flight += record.bytes_sent
        self.spend_budget(record.bytes_sent, now=self.now() if now is None else now)
        if not record.controller_notified:
            self.congestion.on_packet_sent(
                PacketSent(
                    now=sent_at,
                    packet=self._packet_info(record),
                    bytes_in_flight=self.bytes_in_flight,
                )
            )
            record.controller_notified = True
        return True

    def discard_space(self, packet_space: str) -> None:
        space = self._space(packet_space)
        for record in list(space.outstanding.values()):
            if record.in_flight:
                self.bytes_in_flight = max(0, self.bytes_in_flight - record.bytes_sent)
        space.outstanding.clear()
        space.loss_time = None
        space.largest_acked = -1
        space.largest_sent = -1

    def _update_rtt(self, latest_rtt: float, ack_delay: float) -> None:
        self.rtt.latest_rtt = latest_rtt
        if not self.rtt.initialized:
            self.rtt.min_rtt = latest_rtt
            self.rtt.smoothed_rtt = latest_rtt
            self.rtt.rttvar = latest_rtt / 2
            self.rtt.initialized = True
            return
        self.rtt.min_rtt = min(self.rtt.min_rtt, latest_rtt)
        adjusted_rtt = latest_rtt
        if latest_rtt > self.rtt.min_rtt + ack_delay:
            adjusted_rtt -= ack_delay
        self.rtt.rttvar = 0.75 * self.rtt.rttvar + 0.25 * abs(self.rtt.smoothed_rtt - adjusted_rtt)
        self.rtt.smoothed_rtt = 0.875 * self.rtt.smoothed_rtt + 0.125 * adjusted_rtt

    def _loss_delay(self) -> float:
        base = max(self.rtt.latest_rtt, self.rtt.smoothed_rtt)
        if base <= 0:
            base = 0.333
        return max(_GRANULARITY, _TIME_THRESHOLD * base)

    def _persistent_congestion_duration(self, *, packet_space: str) -> float:
        return self.pto_timeout(packet_space=packet_space) * _PERSISTENT_CONGESTION_THRESHOLD

    def _on_congestion_event(self, lost_records: list[PacketRecord], *, now: float, packet_space: str) -> None:
        if not lost_records:
            return
        self.congestion.on_packets_lost(
            PacketsLost(
                now=now,
                packets=tuple(self._packet_info(record) for record in lost_records),
                bytes_lost=sum(record.bytes_sent for record in lost_records if record.in_flight),
                bytes_in_flight=self.bytes_in_flight,
                packet_space=packet_space,
            )
        )
        ack_eliciting_lost = [record for record in sorted(lost_records, key=lambda item: item.sent_time) if record.ack_eliciting]
        if len(ack_eliciting_lost) >= 2:
            duration = ack_eliciting_lost[-1].sent_time - ack_eliciting_lost[0].sent_time
            if duration >= self._persistent_congestion_duration(packet_space=packet_space):
                self.persistent_congestion = True
                self.persistent_congestion_total += 1
                self.congestion.on_persistent_congestion(
                    PersistentCongestion(
                        now=now,
                        packet_space=packet_space,
                        duration=duration,
                    )
                )

    def on_ack_received(
        self,
        acked_numbers: list[int],
        *,
        ack_delay: float = 0.0,
        now: float | None = None,
        packet_space: str = 'application',
    ) -> list[int]:
        if not acked_numbers:
            return []
        at = self.now() if now is None else now
        space = self._space(packet_space)
        acked = sorted(set(acked_numbers))
        largest = acked[-1]
        if largest in space.outstanding:
            sample = max(0.0, at - space.outstanding[largest].sent_time)
            adjusted_ack_delay = min(ack_delay, self.rtt.max_ack_delay) if space.name == 'application' else 0.0
            self._update_rtt(sample, adjusted_ack_delay)
        bytes_acked = 0
        acked_records: list[PacketRecord] = []
        for packet_number in acked:
            record = space.outstanding.pop(packet_number, None)
            if record is None:
                continue
            acked_records.append(record)
            if record.in_flight:
                self.bytes_in_flight = max(0, self.bytes_in_flight - record.bytes_sent)
                bytes_acked += record.bytes_sent
        space.largest_acked = max(space.largest_acked, largest)
        self.congestion.on_ack_received(
            AckReceived(
                now=at,
                packets=tuple(self._packet_info(record) for record in acked_records),
                bytes_acked=bytes_acked,
                bytes_in_flight=self.bytes_in_flight,
                latest_rtt=self.rtt.latest_rtt,
                min_rtt=self.rtt.min_rtt,
                smoothed_rtt=self.rtt.smoothed_rtt,
                rttvar=self.rtt.rttvar,
            )
        )
        self.pto_count = 0
        self.persistent_congestion = False
        return self.detect_lost_packets(now=at, packet_space=space.name)

    def detect_lost_packets(self, *, now: float | None = None, packet_space: str | None = None) -> list[int]:
        at = self.now() if now is None else now
        spaces = [self._space(packet_space)] if packet_space is not None else list(self.spaces.values())
        lost: list[int] = []
        loss_delay = self._loss_delay()
        for space in spaces:
            if space.largest_acked < 0:
                space.loss_time = None
                continue
            space_lost_records: list[PacketRecord] = []
            earliest_loss_time: float | None = None
            for packet_number, record in sorted(space.outstanding.items()):
                if not record.in_flight:
                    continue
                packet_threshold_lost = packet_number <= (space.largest_acked - _PACKET_THRESHOLD)
                time_threshold_lost = record.sent_time <= (at - loss_delay)
                if packet_threshold_lost or time_threshold_lost:
                    space_lost_records.append(record)
                    if record.in_flight:
                        self.bytes_in_flight = max(0, self.bytes_in_flight - record.bytes_sent)
                    lost.append(packet_number)
                else:
                    candidate = record.sent_time + loss_delay
                    earliest_loss_time = candidate if earliest_loss_time is None else min(earliest_loss_time, candidate)
            for record in space_lost_records:
                space.outstanding.pop(record.packet_number, None)
            if space_lost_records:
                self._on_congestion_event(space_lost_records, now=at, packet_space=space.name)
            space.loss_time = earliest_loss_time
        return sorted(lost)

    def pto_timeout(self, *, packet_space: str = 'application') -> float:
        smoothed = self.rtt.smoothed_rtt or self.rtt.latest_rtt or 0.333
        rttvar = self.rtt.rttvar or (smoothed / 2)
        max_ack_delay = self.rtt.max_ack_delay if self._space(packet_space).name == 'application' else 0.0
        return smoothed + max(4 * rttvar, _GRANULARITY) + max_ack_delay

    def next_pto_deadline(self, *, now: float | None = None) -> float | None:
        at = self.now() if now is None else now
        deadline: float | None = None
        for space in self.spaces.values():
            ack_eliciting_packets = [record for record in space.outstanding.values() if record.ack_eliciting and record.in_flight]
            if not ack_eliciting_packets:
                continue
            oldest = min(record.sent_time for record in ack_eliciting_packets)
            candidate = oldest + (self.pto_timeout(packet_space=space.name) * (2**self.pto_count))
            deadline = candidate if deadline is None else min(deadline, candidate)
        if deadline is None:
            return None
        return max(0.0, deadline - at)

    def on_pto_expired(self) -> None:
        self.pto_count += 1

    def pto_candidates(self, *, now: float | None = None) -> list[tuple[str, float]]:
        at = self.now() if now is None else now
        candidates: list[tuple[str, float]] = []
        for space in self.spaces.values():
            ack_eliciting_packets = [record for record in space.outstanding.values() if record.ack_eliciting and record.in_flight]
            if not ack_eliciting_packets:
                continue
            oldest = min(record.sent_time for record in ack_eliciting_packets)
            deadline = oldest + (self.pto_timeout(packet_space=space.name) * (2**self.pto_count))
            candidates.append((space.name, max(at, deadline)))
        return candidates

    def pto_due_spaces(self, *, now: float | None = None) -> list[str]:
        at = self.now() if now is None else now
        candidates = self.pto_candidates(now=at)
        if not candidates:
            return []
        earliest = min(deadline for _space, deadline in candidates)
        return [space for space, deadline in candidates if deadline <= at + _GRANULARITY and abs(deadline - earliest) <= _GRANULARITY]

    def snapshot(self) -> RecoverySnapshot:
        earliest_loss_time: float | None = None
        for space in self.spaces.values():
            if space.loss_time is None:
                continue
            earliest_loss_time = space.loss_time if earliest_loss_time is None else min(earliest_loss_time, space.loss_time)
        return RecoverySnapshot(
            bytes_in_flight=self.bytes_in_flight,
            congestion_window=self.congestion_window,
            ssthresh=self.ssthresh,
            smoothed_rtt=self.rtt.smoothed_rtt,
            rttvar=self.rtt.rttvar,
            latest_rtt=self.rtt.latest_rtt,
            pto_count=self.pto_count,
            outstanding_packets=len(self.outstanding),
            pacing_rate=self.pacing_rate,
            pacing_budget=self.pacing_budget,
            persistent_congestion=self.persistent_congestion,
            earliest_loss_time=earliest_loss_time,
        )


RECOVERY_PRESSURE_CERTIFICATION_SCOPES: tuple[str, ...] = ('loss-recovery-under-pressure', 'pto-backpressure-interaction')

QUIC_RECOVERY_RULES: tuple[dict[str, object], ...] = (
    {
        'rule': 'packet-threshold-loss',
        'value': _PACKET_THRESHOLD,
        'notes': 'packets older than packet threshold behind largest_acked are declared lost',
    },
    {
        'rule': 'time-threshold-loss',
        'value': _TIME_THRESHOLD,
        'notes': 'loss delay is 9/8 of the max(latest_rtt, smoothed_rtt)',
    },
    {
        'rule': 'pto-base',
        'value': 'smoothed_rtt + max(4*rttvar, granularity) + max_ack_delay(application only)',
        'notes': 'PTO doubles with pto_count and excludes max_ack_delay outside application space',
    },
    {
        'rule': 'persistent-congestion-threshold',
        'value': _PERSISTENT_CONGESTION_THRESHOLD,
        'notes': 'persistent congestion spans three PTO intervals',
    },
    {
        'rule': 'pacing-budget',
        'value': 'congestion-window-bounded token bucket',
        'notes': 'send pacing budget is refreshed over time and never exceeds congestion window',
    },
)


