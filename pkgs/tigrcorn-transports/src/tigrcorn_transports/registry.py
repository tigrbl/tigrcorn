from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Iterable, Mapping

from .base import TransportDescriptor


TRANSPORTS = {
    "tcp": TransportDescriptor(name="tcp", multiplexed=False),
    "udp": TransportDescriptor(name="udp", multiplexed=False),
    "unix": TransportDescriptor(name="unix", multiplexed=False),
    "pipe": TransportDescriptor(name="pipe", multiplexed=False),
    "inproc": TransportDescriptor(name="inproc", multiplexed=False),
    "quic": TransportDescriptor(name="quic", multiplexed=True),
}


class TransportDomainError(ValueError):
    """Raised when a transport domain request fails closed."""


@dataclass(frozen=True, slots=True)
class TransportDomainCapabilities:
    datagrams: bool
    streams: bool
    backpressure: bool
    zero_copy: bool
    multiplexing: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "backpressure": self.backpressure,
            "datagrams": self.datagrams,
            "multiplexing": self.multiplexing,
            "streams": self.streams,
            "zero_copy": self.zero_copy,
        }


@dataclass(frozen=True, slots=True)
class TransportDomainRecord:
    domain_id: str
    transport_kind: str
    owner_package: str
    implementation_state: str
    certification_state: str
    capabilities: TransportDomainCapabilities
    evidence_ids: tuple[str, ...] = ()
    quic_specific_evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities.as_dict(),
            "certification_state": self.certification_state,
            "domain_id": self.domain_id,
            "evidence_ids": list(self.evidence_ids),
            "implementation_state": self.implementation_state,
            "owner_package": self.owner_package,
            "quic_specific_evidence_ids": list(self.quic_specific_evidence_ids),
            "transport_kind": self.transport_kind,
        }


@dataclass(frozen=True, slots=True)
class BackpressureObservation:
    domain_id: str
    high_watermark: int
    queued_bytes: int

    @property
    def enforced(self) -> bool:
        return self.queued_bytes >= self.high_watermark

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": "pause_reads" if self.enforced else "accept",
            "domain_id": self.domain_id,
            "enforced": self.enforced,
            "high_watermark": self.high_watermark,
            "queued_bytes": self.queued_bytes,
        }


@dataclass(slots=True)
class DomainResourceAccounting:
    domain_id: str
    connections: int = 0
    streams: int = 0
    datagrams: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    failures: int = 0

    def add(
        self,
        *,
        connections: int = 0,
        streams: int = 0,
        datagrams: int = 0,
        bytes_in: int = 0,
        bytes_out: int = 0,
        failures: int = 0,
    ) -> None:
        for name, value in {
            "connections": connections,
            "streams": streams,
            "datagrams": datagrams,
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "failures": failures,
        }.items():
            if value < 0:
                raise TransportDomainError(f"{name} must be non-negative")
        self.connections += connections
        self.streams += streams
        self.datagrams += datagrams
        self.bytes_in += bytes_in
        self.bytes_out += bytes_out
        self.failures += failures

    def as_dict(self) -> dict[str, int | str]:
        return {
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "connections": self.connections,
            "datagrams": self.datagrams,
            "domain_id": self.domain_id,
            "failures": self.failures,
            "streams": self.streams,
        }


@dataclass(slots=True)
class TransportDomainAccounting:
    _domains: dict[str, DomainResourceAccounting] = field(default_factory=dict)

    def record(self, domain_id: str, **counters: int) -> dict[str, int | str]:
        _require_domain(domain_id)
        accounting = self._domains.setdefault(domain_id, DomainResourceAccounting(domain_id))
        accounting.add(**counters)
        return accounting.as_dict()

    def snapshot(self) -> dict[str, dict[str, int | str]]:
        return {
            domain_id: self._domains.get(domain_id, DomainResourceAccounting(domain_id)).as_dict()
            for domain_id in _DOMAIN_ORDER
        }


_DOMAIN_ORDER: tuple[str, ...] = (
    "tcp",
    "udp",
    "unix",
    "pipe",
    "in-process",
    "listener",
    "quic",
)

_DOMAINS: dict[str, TransportDomainRecord] = {
    "tcp": TransportDomainRecord(
        domain_id="tcp",
        transport_kind="tcp",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="certified",
        capabilities=TransportDomainCapabilities(
            datagrams=False,
            streams=True,
            backpressure=True,
            zero_copy=False,
            multiplexing=False,
        ),
        evidence_ids=("evd:surface-tcp-tls13-backend-control-runtime-boundary",),
    ),
    "udp": TransportDomainRecord(
        domain_id="udp",
        transport_kind="udp",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=True,
            streams=False,
            backpressure=False,
            zero_copy=False,
            multiplexing=False,
        ),
        evidence_ids=("evd:generic-datagram-runtime-pytest",),
    ),
    "unix": TransportDomainRecord(
        domain_id="unix",
        transport_kind="unix",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=False,
            streams=True,
            backpressure=True,
            zero_copy=False,
            multiplexing=False,
        ),
    ),
    "pipe": TransportDomainRecord(
        domain_id="pipe",
        transport_kind="pipe",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=False,
            streams=True,
            backpressure=True,
            zero_copy=False,
            multiplexing=False,
        ),
    ),
    "in-process": TransportDomainRecord(
        domain_id="in-process",
        transport_kind="inproc",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=True,
            streams=True,
            backpressure=True,
            zero_copy=True,
            multiplexing=False,
        ),
    ),
    "listener": TransportDomainRecord(
        domain_id="listener",
        transport_kind="listener",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=False,
            streams=False,
            backpressure=True,
            zero_copy=False,
            multiplexing=False,
        ),
    ),
    "quic": TransportDomainRecord(
        domain_id="quic",
        transport_kind="quic",
        owner_package="tigrcorn-transports",
        implementation_state="implemented",
        certification_state="implemented",
        capabilities=TransportDomainCapabilities(
            datagrams=True,
            streams=True,
            backpressure=True,
            zero_copy=False,
            multiplexing=True,
        ),
        evidence_ids=("evd:corpus-quic-datagram-frame",),
        quic_specific_evidence_ids=(),
    ),
}


def _require_domain(domain_id: str) -> TransportDomainRecord:
    try:
        return _DOMAINS[domain_id]
    except KeyError as exc:
        raise TransportDomainError(f"unsupported transport domain: {domain_id}") from exc


def transport_domains() -> tuple[TransportDomainRecord, ...]:
    return tuple(_DOMAINS[domain_id] for domain_id in _DOMAIN_ORDER)


def export_transport_domains(*, profile: str | None = None) -> dict[str, Any]:
    allowed_domains = None
    if profile is not None:
        allowed_domains = profile_allowed_transport_domains(profile)
    domains = [
        record.as_dict()
        for record in transport_domains()
        if allowed_domains is None or record.domain_id in allowed_domains
    ]
    return {
        "domains": domains,
        "profile": profile,
        "registry_id": "tigrcorn.transport.certification-domains",
        "schema_version": 1,
    }


def transport_domain_diagnostics(
    domain_id: str | None = None,
    *,
    accounting: TransportDomainAccounting | Mapping[str, Mapping[str, Any]] | None = None,
    active_domains: Iterable[str] = (),
    endpoint_identities: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    records = transport_domains() if domain_id is None else (_require_domain(domain_id),)
    active = set(active_domains)
    endpoint_identities = endpoint_identities or {}
    return {
        "diagnostics": [
            {
                "backpressure": record.capabilities.backpressure,
                "carrier_state": "active" if record.domain_id in active else "inactive",
                "certification_state": record.certification_state,
                "domain_id": record.domain_id,
                "endpoint_identity": endpoint_identities.get(record.domain_id),
                "resource_counters": _diagnostic_resource_counters(record.domain_id, accounting),
                "transport_kind": record.transport_kind,
            }
            for record in records
        ],
        "registry_id": "tigrcorn.transport.diagnostics",
        "schema_version": 1,
    }


def _diagnostic_resource_counters(
    domain_id: str,
    accounting: TransportDomainAccounting | Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, int]:
    if accounting is None:
        payload: Mapping[str, Any] = {}
    elif isinstance(accounting, TransportDomainAccounting):
        payload = accounting.snapshot().get(domain_id, {})
    else:
        payload = accounting.get(domain_id, {})
    return {
        "bytes_in": int(payload.get("bytes_in", 0) or 0),
        "bytes_out": int(payload.get("bytes_out", 0) or 0),
        "connections": int(payload.get("connections", 0) or 0),
        "datagrams": int(payload.get("datagrams", 0) or 0),
        "failures": int(payload.get("failures", 0) or 0),
        "streams": int(payload.get("streams", 0) or 0),
    }


def observe_backpressure(
    domain_id: str,
    *,
    queued_bytes: int,
    high_watermark: int,
) -> dict[str, Any]:
    record = _require_domain(domain_id)
    if queued_bytes < 0 or high_watermark < 0:
        raise TransportDomainError("backpressure counters must be non-negative")
    if not record.capabilities.backpressure:
        return {
            "action": "unsupported",
            "domain_id": domain_id,
            "enforced": False,
            "high_watermark": high_watermark,
            "queued_bytes": queued_bytes,
        }
    return BackpressureObservation(
        domain_id=domain_id,
        queued_bytes=queued_bytes,
        high_watermark=high_watermark,
    ).as_dict()


def profile_allowed_transport_domains(profile: str) -> tuple[str, ...]:
    data = _load_profile(profile)
    kinds = {
        _normalize_listener_kind(listener.get("kind", ""))
        for listener in data.get("effective_config", {}).get("listeners", [])
    }
    protocols = {
        protocol
        for listener in data.get("effective_config", {}).get("listeners", [])
        for protocol in listener.get("protocols", [])
    }
    allowed = {"listener", *kinds}
    if "quic" in protocols:
        allowed.add("quic")
    return tuple(domain_id for domain_id in _DOMAIN_ORDER if domain_id in allowed)


def validate_profile_transport_domains(
    profile: str,
    *,
    required_domains: Iterable[str],
) -> dict[str, Any]:
    allowed = set(profile_allowed_transport_domains(profile))
    required = tuple(required_domains)
    unsupported = tuple(domain_id for domain_id in required if domain_id not in _DOMAINS)
    disallowed = tuple(domain_id for domain_id in required if domain_id in _DOMAINS and domain_id not in allowed)
    if unsupported or disallowed:
        raise TransportDomainError(
            "unsupported or disallowed transport domains: "
            + ", ".join((*unsupported, *disallowed))
        )
    return {
        "allowed_domains": tuple(domain_id for domain_id in _DOMAIN_ORDER if domain_id in allowed),
        "profile": profile,
        "required_domains": required,
        "valid": True,
    }


def validate_transport_domain_certification(
    domain_id: str,
    *,
    evidence_ids: Iterable[str] = (),
    quic_specific_evidence_ids: Iterable[str] = (),
) -> dict[str, Any]:
    record = _require_domain(domain_id)
    evidence = tuple(evidence_ids or record.evidence_ids)
    quic_evidence = tuple(quic_specific_evidence_ids or record.quic_specific_evidence_ids)
    missing: list[str] = []
    if not evidence:
        missing.append("transport evidence")
    if record.domain_id == "quic" and not quic_evidence:
        missing.append("QUIC-specific evidence")
    if missing:
        raise TransportDomainError(
            f"{domain_id} cannot be certified without " + " and ".join(missing)
        )
    return {
        "certification_state": "certified",
        "domain_id": domain_id,
        "evidence_ids": evidence,
        "quic_specific_evidence_ids": quic_evidence,
    }


def validate_transport_domain_isolation(
    failed_domain_id: str,
    candidate_domain_id: str,
) -> dict[str, Any]:
    failed = _require_domain(failed_domain_id)
    candidate = _require_domain(candidate_domain_id)
    return {
        "candidate_certification_state": candidate.certification_state,
        "candidate_domain_id": candidate.domain_id,
        "failed_domain_id": failed.domain_id,
        "isolated": failed.domain_id != candidate.domain_id,
    }


def _load_profile(profile: str) -> Mapping[str, Any]:
    profile_name = f"{profile}.profile.json"
    try:
        text = resources.files("tigrcorn.profiles").joinpath(profile_name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise TransportDomainError(f"unknown transport profile: {profile}") from exc
    return json.loads(text)


def _normalize_listener_kind(kind: str) -> str:
    return "in-process" if kind == "inproc" else kind
