from __future__ import annotations

import json

import pytest

from tigrcorn.transports.registry import (
    TransportDomainAccounting,
    TransportDomainError,
    export_transport_domains,
    observe_backpressure,
    profile_allowed_transport_domains,
    transport_domain_diagnostics,
    transport_domains,
    validate_profile_transport_domains,
    validate_transport_domain_certification,
    validate_transport_domain_isolation,
)


def test_transport_domain_registry_shape() -> None:
    domains = {record.domain_id: record for record in transport_domains()}

    assert tuple(domains) == (
        "tcp",
        "udp",
        "unix",
        "pipe",
        "in-process",
        "listener",
        "quic",
    )
    assert domains["tcp"].owner_package == "tigrcorn-transports"
    assert domains["quic"].transport_kind == "quic"
    assert domains["listener"].implementation_state == "implemented"


def test_transport_domain_deterministic_export() -> None:
    first = export_transport_domains()
    second = export_transport_domains()

    assert first == second
    assert json.dumps(first, sort_keys=True)
    assert [domain["domain_id"] for domain in first["domains"]] == [
        "tcp",
        "udp",
        "unix",
        "pipe",
        "in-process",
        "listener",
        "quic",
    ]


def test_transport_domain_capability_discovery() -> None:
    capabilities = {
        domain["domain_id"]: domain["capabilities"]
        for domain in export_transport_domains()["domains"]
    }

    for domain_capabilities in capabilities.values():
        assert set(domain_capabilities) == {
            "backpressure",
            "datagrams",
            "multiplexing",
            "streams",
            "zero_copy",
        }
    assert capabilities["udp"]["datagrams"] is True
    assert capabilities["tcp"]["streams"] is True
    assert capabilities["in-process"]["zero_copy"] is True
    assert capabilities["quic"]["multiplexing"] is True


def test_transport_domain_diagnostics_output() -> None:
    diagnostics = transport_domain_diagnostics()

    assert diagnostics["registry_id"] == "tigrcorn.transport.diagnostics"
    for entry in diagnostics["diagnostics"]:
        assert set(entry) == {
            "backpressure",
            "carrier_state",
            "certification_state",
            "domain_id",
            "endpoint_identity",
            "resource_counters",
            "transport_kind",
        }
        assert set(entry["resource_counters"]) == {
            "bytes_in",
            "bytes_out",
            "connections",
            "datagrams",
            "failures",
            "streams",
        }


def test_transport_domain_profile_selection() -> None:
    assert profile_allowed_transport_domains("default") == ("tcp", "listener")
    assert profile_allowed_transport_domains("strict-h1-origin") == ("tcp", "listener")
    assert profile_allowed_transport_domains("strict-h3-edge") == (
        "tcp",
        "udp",
        "listener",
        "quic",
    )

    exported = export_transport_domains(profile="strict-h3-edge")
    assert [domain["domain_id"] for domain in exported["domains"]] == [
        "tcp",
        "udp",
        "listener",
        "quic",
    ]


def test_transport_domain_backpressure() -> None:
    enforced = observe_backpressure("tcp", queued_bytes=4096, high_watermark=4096)
    accepted = observe_backpressure("tcp", queued_bytes=1024, high_watermark=4096)
    unsupported = observe_backpressure("udp", queued_bytes=4096, high_watermark=4096)

    assert enforced["enforced"] is True
    assert enforced["action"] == "pause_reads"
    assert accepted["enforced"] is False
    assert accepted["action"] == "accept"
    assert unsupported["action"] == "unsupported"


def test_transport_domain_resource_accounting() -> None:
    accounting = TransportDomainAccounting()

    tcp = accounting.record("tcp", connections=1, streams=1, bytes_in=128)
    udp = accounting.record("udp", datagrams=3, bytes_out=384)
    tcp_again = accounting.record("tcp", streams=2, bytes_out=256)
    snapshot = accounting.snapshot()

    assert tcp["connections"] == 1
    assert udp["datagrams"] == 3
    assert tcp_again["streams"] == 3
    assert snapshot["tcp"]["bytes_in"] == 128
    assert snapshot["udp"]["bytes_out"] == 384
    assert snapshot["quic"]["connections"] == 0


def test_transport_domain_strict_profile_fail_closed() -> None:
    with pytest.raises(TransportDomainError, match="quic"):
        validate_profile_transport_domains(
            "strict-h1-origin",
            required_domains=("tcp", "quic"),
        )

    with pytest.raises(TransportDomainError, match="unsupported"):
        validate_profile_transport_domains(
            "strict-h3-edge",
            required_domains=("tcp", "sctp"),
        )

    valid = validate_profile_transport_domains(
        "strict-h3-edge",
        required_domains=("tcp", "udp", "quic"),
    )
    assert valid["valid"] is True


def test_transport_domain_quic_not_certified_without_evidence() -> None:
    with pytest.raises(TransportDomainError, match="QUIC-specific evidence"):
        validate_transport_domain_certification(
            "quic",
            evidence_ids=("evd:generic-transport",),
        )

    result = validate_transport_domain_certification(
        "quic",
        evidence_ids=("evd:generic-transport",),
        quic_specific_evidence_ids=("evd:quic-rfc9000-interop",),
    )
    assert result["certification_state"] == "certified"


def test_transport_domain_cross_domain_isolation() -> None:
    isolation = validate_transport_domain_isolation("udp", "tcp")

    assert isolation == {
        "candidate_certification_state": "certified",
        "candidate_domain_id": "tcp",
        "failed_domain_id": "udp",
        "isolated": True,
    }
    assert validate_transport_domain_isolation("tcp", "tcp")["isolated"] is False
