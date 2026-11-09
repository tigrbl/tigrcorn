from __future__ import annotations

from tigrcorn_quic_cc import PacketInfo

from .model import PacketRecord


class QuicRecoveryCongestionMixin:
    @property
    def congestion_window(self) -> int:
        return self.congestion.congestion_window

    @congestion_window.setter
    def congestion_window(self, value: int) -> None:
        self.congestion.congestion_window = value

    @property
    def minimum_congestion_window(self) -> int:
        return 2 * self.max_datagram_size

    @property
    def ssthresh(self) -> int:
        return self.congestion.ssthresh

    @property
    def pacing_rate(self) -> float:
        return self.congestion.pacing_rate

    @property
    def pacing_budget(self) -> float:
        return self.congestion.pacing_budget

    @pacing_budget.setter
    def pacing_budget(self, value: float) -> None:
        self.congestion.pacing_budget = value

    def available_send_budget(self, *, now: float | None = None) -> float:
        at = self.now() if now is None else now
        limits = self.congestion.limits(now=at)
        if limits is None:
            return 0.0
        self.congestion.pacer.refresh(
            now=at,
            pacing_rate=limits.pacing_rate,
            congestion_window=limits.congestion_window,
        )
        return self.congestion.pacing_budget

    def can_send(self, bytes_sent: int, *, now: float | None = None) -> bool:
        at = self.now() if now is None else now
        return self.congestion.can_send(
            bytes_sent,
            bytes_in_flight=self.bytes_in_flight,
            now=at,
        )

    def time_until_send(self, bytes_sent: int, *, now: float | None = None) -> float | None:
        at = self.now() if now is None else now
        return self.congestion.time_until_send(
            bytes_sent,
            bytes_in_flight=self.bytes_in_flight,
            now=at,
        )

    def spend_budget(self, bytes_sent: int, *, now: float | None = None) -> None:
        self.congestion.spend(bytes_sent, now=self.now() if now is None else now)

    def refund_budget(self, bytes_sent: int, *, now: float | None = None) -> None:
        self.congestion.refund(bytes_sent, now=self.now() if now is None else now)

    @staticmethod
    def _packet_info(record: PacketRecord) -> PacketInfo:
        return PacketInfo(
            packet_number=record.packet_number,
            sent_time=record.sent_time,
            bytes_sent=record.bytes_sent,
            ack_eliciting=record.ack_eliciting,
            packet_space=record.packet_space,
        )

    def update_max_datagram_size(self, value: int, *, now: float | None = None) -> None:
        self.max_datagram_size = value
        self.congestion.update_mtu(value, now=now)
