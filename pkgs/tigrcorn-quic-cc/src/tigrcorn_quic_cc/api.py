from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, runtime_checkable

from .models import (
    AckReceived,
    ControllerContext,
    ControllerSnapshot,
    EcnFeedback,
    MtuUpdated,
    PacketSent,
    PacketsLost,
    PersistentCongestion,
    ProviderMetadata,
    SendLimits,
)

Clock = Callable[[], float]


@runtime_checkable
class CongestionController(Protocol):
    def on_packet_sent(self, event: PacketSent) -> None: ...

    def on_ack_received(self, event: AckReceived) -> None: ...

    def on_packets_lost(self, event: PacketsLost) -> None: ...

    def on_persistent_congestion(self, event: PersistentCongestion) -> None: ...

    def on_ecn_feedback(self, event: EcnFeedback) -> None: ...

    def on_mtu_updated(self, event: MtuUpdated) -> None: ...

    def send_limits(self, now: float) -> SendLimits: ...

    def snapshot(self) -> ControllerSnapshot: ...


@runtime_checkable
class CongestionControllerFactory(Protocol):
    @property
    def metadata(self) -> ProviderMetadata: ...

    def validate_options(self, options: Mapping[str, object]) -> Mapping[str, object]: ...

    def create(
        self,
        context: ControllerContext,
        options: Mapping[str, object],
        *,
        clock: Clock | None = None,
    ) -> CongestionController: ...
