from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tigrcorn_quic_cc import (
    CongestionControllerFactory,
    ProviderMetadata,
    ProviderRegistry,
)
from tigrcorn_quic_cc_reno import factory as reno_factory


@dataclass(frozen=True, slots=True)
class ResolvedCongestionControl:
    factory: CongestionControllerFactory
    options: Mapping[str, object]
    metadata: ProviderMetadata


def resolve_congestion_control(
    algorithm_id: str,
    options: Mapping[str, object] | None = None,
) -> ResolvedCongestionControl:
    """Resolve and validate one provider during listener construction."""

    discovered = ProviderRegistry()
    registry = (
        discovered
        if algorithm_id in discovered.provider_names()
        else ProviderRegistry(builtins={"reno": reno_factory})
    )
    factory = registry.resolve(algorithm_id)
    validated_options = factory.validate_options(options or {})
    return ResolvedCongestionControl(
        factory=factory,
        options=dict(validated_options),
        metadata=factory.metadata,
    )


__all__ = ["ResolvedCongestionControl", "resolve_congestion_control"]
