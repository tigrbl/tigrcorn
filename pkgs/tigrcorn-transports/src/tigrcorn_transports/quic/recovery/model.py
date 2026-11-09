from __future__ import annotations

from dataclasses import dataclass, field

_PACKET_THRESHOLD = 3
_TIME_THRESHOLD = 9 / 8
_GRANULARITY = 0.001
_PERSISTENT_CONGESTION_THRESHOLD = 3


@dataclass(slots=True)
class PacketRecord:
    packet_number: int
    sent_time: float
    bytes_sent: int
    ack_eliciting: bool = True
    in_flight: bool = True
    packet_space: str = 'application'
    is_pto_probe: bool = False
    controller_notified: bool = False


@dataclass(slots=True)
class LossSpace:
    name: str
    outstanding: dict[int, PacketRecord] = field(default_factory=dict)
    largest_acked: int = -1
    largest_sent: int = -1
    loss_time: float | None = None


@dataclass(slots=True)
class RttStats:
    latest_rtt: float = 0.0
    min_rtt: float = 0.0
    smoothed_rtt: float = 0.0
    rttvar: float = 0.0
    max_ack_delay: float = 0.025
    initialized: bool = False


@dataclass(slots=True)
class RecoverySnapshot:
    bytes_in_flight: int
    congestion_window: int
    ssthresh: int
    smoothed_rtt: float
    rttvar: float
    latest_rtt: float
    pto_count: int
    outstanding_packets: int
    pacing_rate: float
    pacing_budget: float
    persistent_congestion: bool
    earliest_loss_time: float | None

