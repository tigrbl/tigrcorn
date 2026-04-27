from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExplicitCertificationSurface:
    feature_id: str
    title: str
    category: str
    evidence_tier: str

    def as_dict(self) -> dict[str, str]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "category": self.category,
            "evidence_tier": self.evidence_tier,
        }


EXPLICIT_CERTIFICATION_SURFACES: tuple[ExplicitCertificationSurface, ...] = (
    ExplicitCertificationSurface("feat:surface-http2-tls-posture", "HTTP/2 TLS posture", "certification", "T4"),
    ExplicitCertificationSurface("feat:surface-https-http11", "HTTPS HTTP/1.1", "certification", "T4"),
    ExplicitCertificationSurface("feat:surface-https-service-identity", "HTTPS service identity", "certification", "T4"),
    ExplicitCertificationSurface(
        "feat:surface-tcp-tls13-external-peer-interop",
        "TCP TLS 1.3 external peer interop",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface(
        "feat:surface-tls13-handshake-messages",
        "TLS 1.3 handshake messages",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface("feat:surface-tls13-record-layer", "TLS 1.3 record layer", "certification", "T4"),
    ExplicitCertificationSurface(
        "feat:surface-tls13-shutdown-behavior",
        "TLS 1.3 shutdown behavior",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface(
        "feat:surface-tls13-state-transition",
        "TLS 1.3 state transition",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface(
        "feat:surface-tls-server-name-indication",
        "TLS server name indication",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface(
        "feat:surface-x509-certificate-profiles",
        "X.509 certificate profiles",
        "certification",
        "T4",
    ),
    ExplicitCertificationSurface("feat:surface-x509-path-validation", "X.509 path validation", "certification", "T4"),
    ExplicitCertificationSurface(
        "feat:surface-http3-control-plane",
        "HTTP/3 control plane",
        "certification_support",
        "T4",
    ),
    ExplicitCertificationSurface("feat:surface-ocsp-policy", "OCSP policy", "certification_support", "T2"),
    ExplicitCertificationSurface("feat:surface-qpack-error-handling", "QPACK error handling", "certification_support", "T4"),
    ExplicitCertificationSurface(
        "feat:surface-quic-retry-token-integrity",
        "QUIC Retry token integrity",
        "certification_support",
        "T4",
    ),
    ExplicitCertificationSurface("feat:surface-quic-tls-mapping", "QUIC TLS mapping", "certification_support", "T4"),
    ExplicitCertificationSurface(
        "feat:surface-tls-status-request-policy",
        "TLS status_request policy",
        "certification_support",
        "T2",
    ),
    ExplicitCertificationSurface(
        "feat:surface-tcp-tls13-backend-control",
        "TCP TLS 1.3 backend control",
        "governance_support",
        "T2",
    ),
    ExplicitCertificationSurface(
        "feat:surface-package-owned-http-fields",
        "Package-owned HTTP fields",
        "operator_surface",
        "T2",
    ),
    ExplicitCertificationSurface("feat:fail-state-registry", "Fail-state registry", "roadmap_feature", "T2"),
    ExplicitCertificationSurface(
        "feat:observability-export-surfaces",
        "Observability export surfaces",
        "roadmap_feature",
        "T2",
    ),
    ExplicitCertificationSurface("feat:origin-negative-corpora", "Origin negative corpora", "roadmap_feature", "T2"),
    ExplicitCertificationSurface("feat:qlog-stance", "qlog stance", "roadmap_feature", "T2"),
    ExplicitCertificationSurface("feat:quic-h3-counters", "QUIC/H3 counters", "roadmap_feature", "T2"),
    ExplicitCertificationSurface("feat:quic-negative-corpora", "QUIC negative corpora", "roadmap_feature", "T2"),
)


def certification_explicit_surface_catalog() -> tuple[dict[str, str], ...]:
    return tuple(surface.as_dict() for surface in EXPLICIT_CERTIFICATION_SURFACES)


def certification_explicit_surface_ids() -> tuple[str, ...]:
    return tuple(surface.feature_id for surface in EXPLICIT_CERTIFICATION_SURFACES)


def validate_explicit_surface_manifest(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    expected = set(certification_explicit_surface_ids())
    actual = set(manifest.get("feature_ids", []))
    if actual != expected:
        failures.append(f"feature_ids mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")
    if manifest.get("boundary_id") != "bnd:certification-explicit-surfaces":
        failures.append("boundary_id must be bnd:certification-explicit-surfaces")
    if manifest.get("status") != "closed":
        failures.append("status must be closed")
    return failures
