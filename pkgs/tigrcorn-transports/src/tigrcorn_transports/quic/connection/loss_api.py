from __future__ import annotations

from .imports import *

class QuicConnectionLossApiMixin:
    def next_pto_deadline(self) -> float | None:
        deadline: float | None = None
        for path_state in self._path_states.values():
            candidate = path_state.recovery.next_pto_deadline()
            if candidate is None:
                continue
            deadline = candidate if deadline is None else min(deadline, candidate)
        return deadline

    def detect_lost_packets(self) -> list[int]:
        lost: list[int] = []
        at = time.monotonic()
        for path_key, path_state in self._path_states.items():
            for packet_space in tuple(path_state.recovery.spaces):
                lost_numbers = path_state.recovery.detect_lost_packets(now=at, packet_space=packet_space)
                if lost_numbers:
                    self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost_numbers)
                    lost.extend(lost_numbers)
        self._update_runtime_timers(now=at)
        return sorted(set(lost))

    def loss_recovery_snapshot(self):
        return self.recovery.snapshot()
