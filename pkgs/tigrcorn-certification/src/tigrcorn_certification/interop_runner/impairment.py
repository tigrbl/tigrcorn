from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UDPImpairmentProfile:
    """Deterministic UDP impairment settings for repeatable QUIC proofs."""

    drop_every: int = 0
    duplicate_every: int = 0
    reorder_every: int = 0
    delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        for name in ("drop_every", "duplicate_every", "reorder_every"):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")


@dataclass(slots=True)
class UDPImpairmentPolicy:
    profile: UDPImpairmentProfile
    _counts: dict[str, int] = field(default_factory=dict)
    _held: dict[str, bytes] = field(default_factory=dict)

    def apply(self, direction: str, payload: bytes) -> tuple[bytes, ...]:
        count = self._counts.get(direction, 0) + 1
        self._counts[direction] = count
        if self.profile.drop_every and count % self.profile.drop_every == 0:
            return ()

        emitted: list[bytes] = []
        held = self._held.pop(direction, None)
        if self.profile.reorder_every and count % self.profile.reorder_every == 0:
            self._held[direction] = bytes(payload)
            if held is not None:
                emitted.append(held)
            return tuple(emitted)

        emitted.append(bytes(payload))
        if held is not None:
            emitted.append(held)
        if self.profile.duplicate_every and count % self.profile.duplicate_every == 0:
            emitted.append(bytes(payload))
        return tuple(emitted)

    def flush(self, direction: str) -> tuple[bytes, ...]:
        held = self._held.pop(direction, None)
        return () if held is None else (held,)


__all__ = ["UDPImpairmentPolicy", "UDPImpairmentProfile"]
