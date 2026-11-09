from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib import metadata as importlib_metadata

from .api import CongestionControllerFactory
from .errors import ProviderDiscoveryError
from .models import ENTRY_POINT_GROUP, ProviderMetadata
from .validation import validate_factory


def _entry_points() -> tuple[importlib_metadata.EntryPoint, ...]:
    discovered = importlib_metadata.entry_points()
    selected: Iterable[importlib_metadata.EntryPoint]
    if hasattr(discovered, "select"):
        selected = discovered.select(group=ENTRY_POINT_GROUP)
    else:  # pragma: no cover - Python/importlib compatibility
        selected = discovered.get(ENTRY_POINT_GROUP, ())
    return tuple(selected)


class ProviderRegistry:
    """Discover providers without importing algorithms that were not selected."""

    def __init__(
        self,
        *,
        entry_points: Iterable[importlib_metadata.EntryPoint] | None = None,
        builtins: Mapping[str, CongestionControllerFactory] | None = None,
    ) -> None:
        self._entry_points = tuple(_entry_points() if entry_points is None else entry_points)
        self._builtins = dict(builtins or {})

    def provider_names(self) -> tuple[str, ...]:
        return tuple(sorted(set(self._builtins) | {item.name for item in self._entry_points}))

    def resolve(self, algorithm_id: str) -> CongestionControllerFactory:
        builtin = self._builtins.get(algorithm_id)
        candidates = [item for item in self._entry_points if item.name == algorithm_id]
        if builtin is not None and candidates:
            raise ProviderDiscoveryError(
                f"duplicate congestion-controller provider id: {algorithm_id!r}"
            )
        if len(candidates) > 1:
            raise ProviderDiscoveryError(
                f"duplicate congestion-controller provider id: {algorithm_id!r}"
            )
        if builtin is not None:
            return validate_factory(builtin)
        if not candidates:
            raise ProviderDiscoveryError(
                f"congestion-controller provider is not installed: {algorithm_id!r}"
            )
        loaded = candidates[0].load()
        factory = loaded() if isinstance(loaded, type) else loaded
        return validate_factory(factory)

    def metadata(self, algorithm_id: str) -> ProviderMetadata:
        return self.resolve(algorithm_id).metadata
