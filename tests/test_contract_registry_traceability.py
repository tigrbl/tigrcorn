from __future__ import annotations

import json

import pytest

from tigrcorn_contract import (
    ContractRecord,
    ContractStability,
    ContractTraceability,
    ContractTraceabilityError,
    TraceabilityStatus,
    contract_records,
    export_contract_registry,
    validate_contract_traceability,
    validate_registry,
)


def _records_by_id() -> dict[str, ContractRecord]:
    return {record.contract_id: record for record in contract_records()}


def test_contract_registry_record_shape() -> None:
    record = _records_by_id()["asgi.http.scope"]
    payload = record.as_dict()

    assert payload["contract_id"] == "asgi.http.scope"
    assert payload["version"] == "1.0"
    assert payload["owner_package"] == "tigrcorn-contract"
    assert payload["owner_module"] == "tigrcorn_contract.scopes"
    assert payload["stability"] == "certified"
    assert payload["implemented"] is True
    assert payload["certified"] is True
    assert {"rfcs", "spec_ids", "implementation_refs", "test_ids", "evidence_ids"} <= set(payload["traceability"])


def test_contract_registry_deterministic_export() -> None:
    first = export_contract_registry()
    second = export_contract_registry()

    assert first == second
    assert [item["contract_id"] for item in first["contracts"]] == sorted(item["contract_id"] for item in first["contracts"])
    assert json.loads(json.dumps(first, sort_keys=True)) == first


def test_contract_registry_stability_levels() -> None:
    stabilities = {record.stability for record in contract_records()}

    assert {
        ContractStability.EXPERIMENTAL,
        ContractStability.PREVIEW,
        ContractStability.STABLE,
        ContractStability.CERTIFIED,
        ContractStability.DEPRECATED,
    } <= stabilities


def test_contract_registry_owning_package_links() -> None:
    for record in contract_records():
        assert record.owner_package.startswith("tigrcorn-")
        assert record.owner_module.startswith(record.owner_package.replace("-", "_"))


def test_contract_registry_certified_vs_implemented() -> None:
    records = _records_by_id()

    assert records["asgi.http.scope"].implemented is True
    assert records["asgi.http.scope"].certified is True
    assert records["asgi.websocket.events"].implemented is True
    assert records["asgi.websocket.events"].certified is False


def test_contract_registry_deprecation_state() -> None:
    deprecated = _records_by_id()["asgi.http.scope.v0"]

    assert deprecated.stability is ContractStability.DEPRECATED
    assert deprecated.implemented is False
    assert deprecated.certified is False
    assert deprecated.replacement_contract_id == "asgi.http.scope"
    assert deprecated.retirement_note


def test_rfc_to_evidence_chain_complete() -> None:
    certified = _records_by_id()["asgi.http.scope"]

    assert certified.traceability.status is TraceabilityStatus.COMPLETE
    assert certified.traceability.release_certified is True
    validate_contract_traceability(certified)
    validate_registry()


def test_rfc_to_evidence_partial_state_explicit() -> None:
    partial = _records_by_id()["operator.contract.registry"]

    assert partial.traceability.status is TraceabilityStatus.PARTIAL
    assert partial.traceability.release_certified is False
    assert partial.certified is False


def test_rfc_to_evidence_provisional_state_explicit() -> None:
    provisional = _records_by_id()["webtransport.stream.identity"]

    assert provisional.traceability.status is TraceabilityStatus.PROVISIONAL
    assert provisional.traceability.release_certified is False
    assert provisional.certified is False


def test_rfc_to_evidence_certified_surface_fails_without_links() -> None:
    broken = ContractRecord(
        contract_id="broken.certified.contract",
        version="1.0",
        title="Broken certified contract",
        owner_package="tigrcorn-contract",
        owner_module="tigrcorn_contract.registry",
        stability=ContractStability.CERTIFIED,
        implemented=True,
        certified=True,
        traceability=ContractTraceability(
            rfcs=("RFC 9110",),
            spec_ids=("spc:2058",),
            implementation_refs=("tigrcorn_contract.registry:export_contract_registry",),
            test_ids=(),
            evidence_ids=(),
            negative_test_ids=(),
            status=TraceabilityStatus.PARTIAL,
        ),
    )

    with pytest.raises(ContractTraceabilityError, match="lacks complete traceability"):
        validate_contract_traceability(broken)


def test_rfc_to_evidence_negative_coverage_links() -> None:
    certified = _records_by_id()["asgi.http.scope"]
    stable = _records_by_id()["asgi.websocket.events"]

    assert "tst:contract-unsupported-scope-rejection" in certified.traceability.negative_test_ids
    assert certified.traceability.negative_test_ids
    assert stable.traceability.negative_test_ids == ()
    assert stable.certified is False
