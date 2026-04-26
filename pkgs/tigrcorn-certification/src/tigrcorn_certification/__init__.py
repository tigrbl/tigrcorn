from __future__ import annotations

PACKAGE_BOUNDARY = "certification"

__all__ = [
    "PACKAGE_BOUNDARY",
    "evaluate_release_gates",
    "assert_release_ready",
    "ReleaseGateError",
    "ReleaseGateReport",
]


def __getattr__(name: str):
    if name in {
        "evaluate_release_gates",
        "assert_release_ready",
        "ReleaseGateError",
        "ReleaseGateReport",
    }:
        from .release_gates import (
            ReleaseGateError,
            ReleaseGateReport,
            assert_release_ready,
            evaluate_release_gates,
        )

        mapping = {
            "evaluate_release_gates": evaluate_release_gates,
            "assert_release_ready": assert_release_ready,
            "ReleaseGateError": ReleaseGateError,
            "ReleaseGateReport": ReleaseGateReport,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
