from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

API_VERSION = "1"
ENTRY_POINT_GROUP = "tigrcorn.quic_cc.v1"


@dataclass(frozen=True, slots=True)
class PacketInfo:
    packet_number: int
    sent_time: float
    bytes_sent: int
    ack_eliciting: bool = True
    packet_space: str = "application"


@dataclass(frozen=True, slots=True)
class ControllerContext:
    max_datagram_size: int
    initial_rtt: float = 0.333
    max_ack_delay: float = 0.025


@dataclass(frozen=True, slots=True)
class PacketSent:
    now: float
    packet: PacketInfo
    bytes_in_flight: int
    application_limited: bool = False


@dataclass(frozen=True, slots=True)
class AckReceived:
    now: float
    packets: tuple[PacketInfo, ...]
    bytes_acked: int
    bytes_in_flight: int
    latest_rtt: float
    min_rtt: float
    smoothed_rtt: float
    rttvar: float
    application_limited: bool = False
    delivery_rate: float | None = None
    ecn_counts: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class PacketsLost:
    now: float
    packets: tuple[PacketInfo, ...]
    bytes_lost: int
    bytes_in_flight: int
    packet_space: str


@dataclass(frozen=True, slots=True)
class PersistentCongestion:
    now: float
    packet_space: str
    duration: float


@dataclass(frozen=True, slots=True)
class EcnFeedback:
    now: float
    ect0: int
    ect1: int
    ce: int
    bytes_in_flight: int


@dataclass(frozen=True, slots=True)
class MtuUpdated:
    now: float
    max_datagram_size: int


@dataclass(frozen=True, slots=True)
class SendLimits:
    congestion_window: int
    pacing_rate: float
    send_quantum: int


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    algorithm: str
    mode: str
    congestion_window: int
    pacing_rate: float
    send_quantum: int
    measurements: Mapping[str, int | float | str | bool | None] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "measurements", MappingProxyType(dict(self.measurements)))


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    algorithm_id: str
    display_name: str
    distribution: str
    distribution_version: str
    api_version: str = API_VERSION
    capabilities: tuple[str, ...] = ()
