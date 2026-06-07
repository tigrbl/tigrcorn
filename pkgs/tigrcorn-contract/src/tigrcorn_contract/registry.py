from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class ContractStability(str, Enum):
    EXPERIMENTAL = "experimental"
    PREVIEW = "preview"
    STABLE = "stable"
    CERTIFIED = "certified"
    DEPRECATED = "deprecated"


class TraceabilityStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    PROVISIONAL = "provisional"
    FAILED = "failed"


class ContractTraceabilityError(ValueError):
    """Raised when a contract claims certification without required proof."""


@dataclass(frozen=True, slots=True)
class ContractTraceability:
    rfcs: tuple[str, ...] = ()
    spec_ids: tuple[str, ...] = ()
    implementation_refs: tuple[str, ...] = ()
    test_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    negative_test_ids: tuple[str, ...] = ()
    status: TraceabilityStatus = TraceabilityStatus.PARTIAL
    release_certified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "rfcs": list(self.rfcs),
            "spec_ids": list(self.spec_ids),
            "implementation_refs": list(self.implementation_refs),
            "test_ids": list(self.test_ids),
            "evidence_ids": list(self.evidence_ids),
            "negative_test_ids": list(self.negative_test_ids),
            "status": self.status.value,
            "release_certified": self.release_certified,
        }


@dataclass(frozen=True, slots=True)
class ContractRecord:
    contract_id: str
    version: str
    title: str
    owner_package: str
    owner_module: str
    stability: ContractStability
    implemented: bool
    certified: bool
    traceability: ContractTraceability
    replacement_contract_id: str | None = None
    retirement_note: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "contract_id": self.contract_id,
            "version": self.version,
            "title": self.title,
            "owner_package": self.owner_package,
            "owner_module": self.owner_module,
            "stability": self.stability.value,
            "implemented": self.implemented,
            "certified": self.certified,
            "traceability": self.traceability.as_dict(),
            "tags": list(self.tags),
        }
        if self.replacement_contract_id is not None:
            payload["replacement_contract_id"] = self.replacement_contract_id
        if self.retirement_note is not None:
            payload["retirement_note"] = self.retirement_note
        return payload


def _traceability_status(
    *,
    rfcs: Iterable[str] = (),
    spec_ids: Iterable[str] = (),
    implementation_refs: Iterable[str] = (),
    test_ids: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
    negative_test_ids: Iterable[str] = (),
    provisional: bool = False,
) -> ContractTraceability:
    traceability = ContractTraceability(
        rfcs=tuple(sorted(rfcs)),
        spec_ids=tuple(sorted(spec_ids)),
        implementation_refs=tuple(sorted(implementation_refs)),
        test_ids=tuple(sorted(test_ids)),
        evidence_ids=tuple(sorted(evidence_ids)),
        negative_test_ids=tuple(sorted(negative_test_ids)),
        status=TraceabilityStatus.PROVISIONAL if provisional else TraceabilityStatus.PARTIAL,
    )
    complete = all(
        (
            traceability.rfcs,
            traceability.spec_ids,
            traceability.implementation_refs,
            traceability.test_ids,
            traceability.evidence_ids,
            traceability.negative_test_ids,
        )
    )
    if complete and not provisional:
        return ContractTraceability(
            rfcs=traceability.rfcs,
            spec_ids=traceability.spec_ids,
            implementation_refs=traceability.implementation_refs,
            test_ids=traceability.test_ids,
            evidence_ids=traceability.evidence_ids,
            negative_test_ids=traceability.negative_test_ids,
            status=TraceabilityStatus.COMPLETE,
            release_certified=True,
        )
    return traceability


_CONTRACTS: tuple[ContractRecord, ...] = (
    ContractRecord(
        contract_id="asgi.http.scope",
        version="1.0",
        title="HTTP scope contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.scopes",
        stability=ContractStability.CERTIFIED,
        implemented=True,
        certified=True,
        traceability=_traceability_status(
            rfcs=("RFC 9110", "RFC 9112"),
            spec_ids=("spc:1021",),
            implementation_refs=("tigrcorn_contract.scopes:contract_scope",),
            test_ids=("tst:contract-http-scope", "tst:contract-unsupported-scope-rejection"),
            evidence_ids=("evd:contract-http-scope-pytest", "evd:contract-unsupported-scope-rejection-pytest"),
            negative_test_ids=("tst:contract-unsupported-scope-rejection",),
        ),
        tags=("http", "scope"),
    ),
    ContractRecord(
        contract_id="asgi.websocket.events",
        version="1.0",
        title="WebSocket event contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.events",
        stability=ContractStability.STABLE,
        implemented=True,
        certified=False,
        traceability=_traceability_status(
            rfcs=("RFC 6455",),
            spec_ids=("spc:1021",),
            implementation_refs=("tigrcorn_contract.events:websocket_connect",),
            test_ids=("tst:contract-websocket-event-map",),
            evidence_ids=("evd:contract-websocket-event-map-pytest",),
        ),
        tags=("websocket", "events"),
    ),
    ContractRecord(
        contract_id="webtransport.stream.identity",
        version="0.9",
        title="WebTransport stream identity contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.metadata",
        stability=ContractStability.PREVIEW,
        implemented=True,
        certified=False,
        traceability=_traceability_status(
            rfcs=("RFC 9220",),
            spec_ids=("spc:1011",),
            implementation_refs=("tigrcorn_contract.metadata:stream_identity",),
            test_ids=("tst:contract-webtransport-stream-identity",),
            evidence_ids=("evd:contract-webtransport-stream-identity-pytest",),
            provisional=True,
        ),
        tags=("webtransport", "identity"),
    ),
    ContractRecord(
        contract_id="operator.contract.registry",
        version="0.1",
        title="Contract registry export contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.registry",
        stability=ContractStability.EXPERIMENTAL,
        implemented=True,
        certified=False,
        traceability=_traceability_status(
            spec_ids=("spc:2058",),
            implementation_refs=("tigrcorn_contract.registry:export_contract_registry",),
            test_ids=("tst:contract-registry-record-shape", "tst:contract-registry-deterministic-export"),
            evidence_ids=("evd:contract-registry-and-traceability-test-plan",),
        ),
        tags=("operator", "registry"),
    ),
    ContractRecord(
        contract_id="asgi.http.scope.v0",
        version="0.9",
        title="Deprecated HTTP scope contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.scopes",
        stability=ContractStability.DEPRECATED,
        implemented=False,
        certified=False,
        traceability=_traceability_status(spec_ids=("spc:1021",)),
        replacement_contract_id="asgi.http.scope",
        retirement_note="Replaced by the certified 1.0 HTTP scope contract.",
        tags=("http", "scope"),
    ),
)


def contract_records() -> tuple[ContractRecord, ...]:
    return tuple(sorted(_CONTRACTS, key=lambda item: item.contract_id))


def export_contract_registry() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "registry": "tigrcorn.contracts",
        "contracts": [record.as_dict() for record in contract_records()],
    }


def validate_contract_traceability(record: ContractRecord) -> None:
    traceability = record.traceability
    missing: list[str] = []
    for field_name in ("rfcs", "spec_ids", "implementation_refs", "test_ids", "evidence_ids", "negative_test_ids"):
        if not getattr(traceability, field_name):
            missing.append(field_name)
    if record.certified and (traceability.status != TraceabilityStatus.COMPLETE or missing):
        raise ContractTraceabilityError(
            f"certified contract {record.contract_id!r} lacks complete traceability: {', '.join(missing)}"
        )
    if record.certified and record.stability != ContractStability.CERTIFIED:
        raise ContractTraceabilityError(f"certified contract {record.contract_id!r} must use certified stability")


def validate_registry(records: Iterable[ContractRecord] | None = None) -> None:
    for record in records if records is not None else contract_records():
        validate_contract_traceability(record)
