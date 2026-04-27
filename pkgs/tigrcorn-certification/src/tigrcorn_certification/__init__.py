from __future__ import annotations

PACKAGE_BOUNDARY = "certification"

__all__ = [
    "PACKAGE_BOUNDARY",
    "evaluate_release_gates",
    "assert_release_ready",
    "ReleaseGateError",
    "ReleaseGateReport",
    "certification_explicit_surface_catalog",
    "certification_explicit_surface_ids",
    "validate_explicit_surface_manifest",
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
    if name in {
        "certification_explicit_surface_catalog",
        "certification_explicit_surface_ids",
        "validate_explicit_surface_manifest",
    }:
        from .explicit_surfaces import (
            certification_explicit_surface_catalog,
            certification_explicit_surface_ids,
            validate_explicit_surface_manifest,
        )

        mapping = {
            "certification_explicit_surface_catalog": certification_explicit_surface_catalog,
            "certification_explicit_surface_ids": certification_explicit_surface_ids,
            "validate_explicit_surface_manifest": validate_explicit_surface_manifest,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
