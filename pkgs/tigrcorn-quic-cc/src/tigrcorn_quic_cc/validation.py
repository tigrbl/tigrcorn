from __future__ import annotations

import math
import re

from .api import CongestionControllerFactory
from .errors import InvalidControllerOutput, ProviderCompatibilityError
from .models import API_VERSION, ProviderMetadata, SendLimits

_ALGORITHM_ID = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")


def validate_provider_metadata(metadata: ProviderMetadata) -> ProviderMetadata:
    if not _ALGORITHM_ID.fullmatch(metadata.algorithm_id):
        raise ProviderCompatibilityError(
            f"invalid congestion-controller algorithm id: {metadata.algorithm_id!r}"
        )
    if metadata.api_version != API_VERSION:
        raise ProviderCompatibilityError(
            f"provider {metadata.algorithm_id!r} targets API {metadata.api_version!r}; "
            f"expected {API_VERSION!r}"
        )
    if not metadata.distribution or not metadata.distribution_version:
        raise ProviderCompatibilityError("provider distribution metadata is incomplete")
    return metadata


def validate_factory(factory: CongestionControllerFactory) -> CongestionControllerFactory:
    validate_provider_metadata(factory.metadata)
    return factory


def validate_send_limits(
    limits: SendLimits,
    *,
    max_datagram_size: int,
) -> SendLimits:
    minimum_window = 2 * max_datagram_size
    if isinstance(limits.congestion_window, bool) or limits.congestion_window < minimum_window:
        raise InvalidControllerOutput(
            f"congestion window must be at least {minimum_window} bytes"
        )
    if not math.isfinite(limits.pacing_rate) or limits.pacing_rate <= 0:
        raise InvalidControllerOutput("pacing rate must be finite and positive")
    if isinstance(limits.send_quantum, bool) or not 0 < limits.send_quantum <= limits.congestion_window:
        raise InvalidControllerOutput(
            "send quantum must be positive and no larger than congestion window"
        )
    return limits
