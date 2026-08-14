from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from tigrcorn_quic_cc import (
    AckReceived,
    CongestionController,
    CongestionControllerFactory,
    ControllerContext,
    ControllerSnapshot,
    EcnFeedback,
    MtuUpdated,
    PacketSent,
    PacketsLost,
    PersistentCongestion,
    SendLimits,
    validate_factory,
    validate_send_limits,
)
from tigrcorn_quic_cc_reno import factory as reno_factory

from .pacer import QuicPacer


class QuicCongestionRuntime:
    """Validates provider policy and enforces it through a transport pacer."""

    def __init__(
        self,
        *,
        max_datagram_size: int,
        factory: CongestionControllerFactory | None = None,
        options: Mapping[str, object] | None = None,
        options_validated: bool = False,
        clock: Callable[[], float] | None = None,
        max_ack_delay: float = 0.025,
    ) -> None:
        self.clock = clock or time.monotonic
        self.factory = validate_factory(factory or reno_factory)
        self.options = (
            dict(options or {})
            if options_validated
            else self.factory.validate_options(options or {})
        )
        self.max_datagram_size = max_datagram_size
        self.controller: CongestionController = self.factory.create(
            ControllerContext(
                max_datagram_size=max_datagram_size,
                max_ack_delay=max_ack_delay,
            ),
            self.options,
            clock=self.clock,
        )
        initial = self._validated_limits(self.clock())
        self.pacer = QuicPacer(initial_budget=float(initial.congestion_window))
        self.failed = False
        self.failure_reason: str | None = None
        self._compat_window_override: int | None = None

    @property
    def metadata(self):
        return self.factory.metadata

    def _fail(self, exc: BaseException) -> None:
        self.failed = True
        self.failure_reason = type(exc).__name__

    def _validated_limits(self, now: float) -> SendLimits:
        return validate_send_limits(
            self.controller.send_limits(now),
            max_datagram_size=self.max_datagram_size,
        )

    def limits(self, *, now: float | None = None) -> SendLimits | None:
        if self.failed:
            return None
        at = self.clock() if now is None else now
        try:
            limits = self._validated_limits(at)
        except Exception as exc:  # noqa: BLE001 - provider boundary must fail closed
            self._fail(exc)
            return None
        if self._compat_window_override is None:
            return limits
        return SendLimits(
            congestion_window=max(0, self._compat_window_override),
            pacing_rate=limits.pacing_rate,
            send_quantum=min(limits.send_quantum, max(1, self._compat_window_override)),
        )

    @property
    def congestion_window(self) -> int:
        limits = self.limits()
        return 0 if limits is None else limits.congestion_window

    @congestion_window.setter
    def congestion_window(self, value: int) -> None:
        self._compat_window_override = int(value)

    @property
    def pacing_rate(self) -> float:
        limits = self.limits()
        return 0.0 if limits is None else limits.pacing_rate

    @property
    def pacing_budget(self) -> float:
        return self.pacer.budget

    @pacing_budget.setter
    def pacing_budget(self, value: float) -> None:
        self.pacer.budget = max(0.0, float(value))

    @property
    def ssthresh(self) -> int:
        if self.failed:
            return 2**31 - 1
        try:
            value = self.controller.snapshot().measurements.get("ssthresh")
        except Exception as exc:  # noqa: BLE001 - provider boundary must fail closed
            self._fail(exc)
            return 2**31 - 1
        return int(value) if isinstance(value, int) else 2**31 - 1

    def _dispatch(self, method: str, event: object) -> None:
        if self.failed:
            return
        try:
            getattr(self.controller, method)(event)
        except Exception as exc:  # noqa: BLE001 - provider boundary must fail closed
            self._fail(exc)

    def on_packet_sent(self, event: PacketSent) -> None:
        self._dispatch("on_packet_sent", event)

    def on_ack_received(self, event: AckReceived) -> None:
        self._dispatch("on_ack_received", event)

    def on_packets_lost(self, event: PacketsLost) -> None:
        self._dispatch("on_packets_lost", event)

    def on_persistent_congestion(self, event: PersistentCongestion) -> None:
        self._dispatch("on_persistent_congestion", event)

    def on_ecn_feedback(self, event: EcnFeedback) -> None:
        self._dispatch("on_ecn_feedback", event)

    def update_mtu(self, max_datagram_size: int, *, now: float | None = None) -> None:
        self.max_datagram_size = max_datagram_size
        self._dispatch(
            "on_mtu_updated",
            MtuUpdated(
                now=self.clock() if now is None else now,
                max_datagram_size=max_datagram_size,
            ),
        )

    def can_send(self, amount: int, *, bytes_in_flight: int, now: float) -> bool:
        limits = self.limits(now=now)
        if limits is None or bytes_in_flight + amount > limits.congestion_window:
            return False
        return self.pacer.time_until_send(
            amount,
            now=now,
            pacing_rate=limits.pacing_rate,
            congestion_window=limits.congestion_window,
        ) == 0.0

    def time_until_send(
        self,
        amount: int,
        *,
        bytes_in_flight: int,
        now: float,
    ) -> float | None:
        limits = self.limits(now=now)
        if limits is None or bytes_in_flight + amount > limits.congestion_window:
            return None
        return self.pacer.time_until_send(
            amount,
            now=now,
            pacing_rate=limits.pacing_rate,
            congestion_window=limits.congestion_window,
        )

    def spend(self, amount: int, *, now: float) -> None:
        limits = self.limits(now=now)
        if limits is None:
            return
        self.pacer.spend(
            amount,
            now=now,
            pacing_rate=limits.pacing_rate,
            congestion_window=limits.congestion_window,
        )

    def refund(self, amount: int, *, now: float) -> None:
        limits = self.limits(now=now)
        if limits is None:
            return
        self.pacer.refund(
            amount,
            now=now,
            pacing_rate=limits.pacing_rate,
            congestion_window=limits.congestion_window,
        )

    def snapshot(self) -> ControllerSnapshot:
        if not self.failed:
            try:
                return self.controller.snapshot()
            except Exception as exc:  # noqa: BLE001 - provider boundary must fail closed
                self._fail(exc)
        return ControllerSnapshot(
            algorithm=self.metadata.algorithm_id,
            mode="failed_closed",
            congestion_window=0,
            pacing_rate=0.0,
            send_quantum=0,
            measurements={"failure_reason": self.failure_reason},
        )
