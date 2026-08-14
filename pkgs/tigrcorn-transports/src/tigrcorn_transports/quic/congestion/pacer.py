from __future__ import annotations


class QuicPacer:
    """Transport-owned token bucket enforcing provider pacing limits."""

    def __init__(self, *, initial_budget: float) -> None:
        self.budget = max(0.0, float(initial_budget))
        self._last_update: float | None = None

    def refresh(self, *, now: float, pacing_rate: float, congestion_window: int) -> None:
        if self._last_update is None:
            self._last_update = now
            self.budget = min(float(congestion_window), self.budget)
            return
        elapsed = max(0.0, now - self._last_update)
        self._last_update = now
        self.budget = min(
            float(congestion_window),
            self.budget + elapsed * pacing_rate,
        )

    def time_until_send(
        self,
        amount: int,
        *,
        now: float,
        pacing_rate: float,
        congestion_window: int,
    ) -> float | None:
        self.refresh(
            now=now,
            pacing_rate=pacing_rate,
            congestion_window=congestion_window,
        )
        if float(amount) <= self.budget:
            return 0.0
        if pacing_rate <= 0:
            return None
        return max(0.0, (float(amount) - self.budget) / pacing_rate)

    def spend(
        self,
        amount: int,
        *,
        now: float,
        pacing_rate: float,
        congestion_window: int,
    ) -> None:
        self.refresh(
            now=now,
            pacing_rate=pacing_rate,
            congestion_window=congestion_window,
        )
        self.budget = max(0.0, self.budget - float(amount))

    def refund(
        self,
        amount: int,
        *,
        now: float,
        pacing_rate: float,
        congestion_window: int,
    ) -> None:
        self.refresh(
            now=now,
            pacing_rate=pacing_rate,
            congestion_window=congestion_window,
        )
        self.budget = min(float(congestion_window), self.budget + float(amount))
