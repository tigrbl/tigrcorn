from __future__ import annotations

from .imports import *

def _percentiles(samples: list[float]) -> tuple[float, float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0, 0.0
    ordered = sorted(samples)
    return (
        _percentile(ordered, 50.0),
        _percentile(ordered, 95.0),
        _percentile(ordered, 99.0),
        _percentile(ordered, 99.9),
    )


def _percentile(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return float(sorted_samples[0])
    rank = (pct / 100.0) * (len(sorted_samples) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_samples) - 1)
    frac = rank - low
    return float(sorted_samples[low] + ((sorted_samples[high] - sorted_samples[low]) * frac))


def _build_histogram(samples: list[float], *, bucket_count: int = 8) -> list[dict[str, Any]]:
    if not samples:
        return []
    values = sorted(samples)
    minimum = values[0]
    maximum = values[-1]
    if minimum == maximum:
        return [{'lower_ms': minimum, 'upper_ms': maximum, 'count': len(values)}]
    span = maximum - minimum
    bucket_size = span / float(bucket_count)
    buckets = [{'lower_ms': minimum + (bucket_size * index), 'upper_ms': minimum + (bucket_size * (index + 1)), 'count': 0} for index in range(bucket_count)]
    for value in values:
        offset = int(min(bucket_count - 1, (value - minimum) / bucket_size))
        buckets[offset]['count'] += 1
    return buckets
