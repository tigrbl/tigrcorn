from __future__ import annotations

from collections.abc import Mapping
from importlib import metadata as importlib_metadata
from types import MappingProxyType

from tigrcorn_quic_cc import (
    Clock,
    CongestionController,
    ControllerContext,
    ProviderConfigurationError,
    ProviderMetadata,
)

from .controller import RenoController


def _version() -> str:
    try:
        return importlib_metadata.version("tigrcorn-quic-cc-reno")
    except importlib_metadata.PackageNotFoundError:
        return "0.3.18.dev2"


class RenoProviderFactory:
    metadata = ProviderMetadata(
        algorithm_id="reno",
        display_name="Reno",
        distribution="tigrcorn-quic-cc-reno",
        distribution_version=_version(),
        capabilities=("slow_start", "congestion_avoidance", "persistent_congestion"),
    )

    def validate_options(self, options: Mapping[str, object]) -> Mapping[str, object]:
        allowed = {
            "initial_window_packets",
            "initial_window_cap_bytes",
            "pacing_gain",
        }
        unknown = sorted(set(options) - allowed)
        if unknown:
            raise ProviderConfigurationError(
                f"unknown Reno congestion-control options: {', '.join(unknown)}"
            )
        normalized: dict[str, object] = {}
        initial_packets = options.get("initial_window_packets", 10)
        initial_cap = options.get("initial_window_cap_bytes", 14_720)
        pacing_gain = options.get("pacing_gain", 1.0)
        if isinstance(initial_packets, bool) or not isinstance(initial_packets, int) or initial_packets < 2:
            raise ProviderConfigurationError("initial_window_packets must be an integer >= 2")
        if isinstance(initial_cap, bool) or not isinstance(initial_cap, int) or initial_cap < 2400:
            raise ProviderConfigurationError("initial_window_cap_bytes must be an integer >= 2400")
        if isinstance(pacing_gain, bool) or not isinstance(pacing_gain, (int, float)) or float(pacing_gain) <= 0:
            raise ProviderConfigurationError("pacing_gain must be a positive number")
        normalized["initial_window_packets"] = initial_packets
        normalized["initial_window_cap_bytes"] = initial_cap
        normalized["pacing_gain"] = float(pacing_gain)
        return MappingProxyType(normalized)

    def create(
        self,
        context: ControllerContext,
        options: Mapping[str, object],
        *,
        clock: Clock | None = None,
    ) -> CongestionController:
        return RenoController(context, options, clock=clock)


factory = RenoProviderFactory()
