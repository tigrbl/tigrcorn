from __future__ import annotations

import json

import pytest

from tigrcorn.transports.quic.security import (
    REQUIRED_ARTIFACT_SECTIONS,
    QuicRetryTokenIssuer,
    QuicSecurityCertificationError,
    anti_amplification_decision,
    certify_quic_operational_security,
    handle_path_validation_event,
    observe_cid_rotation,
    quic_loss_recovery_evidence,
    quic_security_certification_artifact,
    quic_security_checks,
    redact_qlog,
    validate_source_address,
)


def test_quic_security_certification_artifact_shape() -> None:
    artifact = quic_security_certification_artifact()
    repeated = quic_security_certification_artifact()

    assert artifact == repeated
    assert artifact["artifact_id"] == "tigrcorn.quic.operational-security"
    assert artifact["schema_version"] == 1
    assert artifact["sections"] == REQUIRED_ARTIFACT_SECTIONS
    for section in REQUIRED_ARTIFACT_SECTIONS:
        assert section in artifact
    assert json.dumps(artifact, sort_keys=True)


def test_quic_security_profile_discovery() -> None:
    checks = quic_security_checks("strict-h3-edge")

    assert checks["profile"] == "strict-h3-edge"
    assert checks["profile_quic"]["require_retry"] is True
    assert "RFC 9000" in checks["rfc_targets"]
    assert "RFC 9002" in checks["rfc_targets"]
    assert {check["id"] for check in checks["checks"]} >= {
        "quic.retry-token",
        "quic.loss-recovery",
        "quic.qlog-redaction",
        "quic.anti-amplification",
        "quic.path-validation",
    }


def test_quic_retry_token_accept_reject() -> None:
    issuer = QuicRetryTokenIssuer(secret=b"test-secret", lifetime_ms=100)
    token = issuer.issue(
        address=("203.0.113.10", 4433),
        original_destination_connection_id=b"odcid",
        issued_at_ms=1_000,
    )

    accepted = issuer.validate(
        token,
        address=("203.0.113.10", 4433),
        now_ms=1_050,
        consume=False,
    )
    assert accepted["accepted"] is True
    assert accepted["address"] == ["203.0.113.10", 4433]
    assert "odcid" not in json.dumps(accepted)

    with pytest.raises(QuicSecurityCertificationError, match="integrity"):
        issuer.validate(token + b"tamper", address=("203.0.113.10", 4433), now_ms=1_050)
    with pytest.raises(QuicSecurityCertificationError, match="stale"):
        issuer.validate(token, address=("203.0.113.10", 4433), now_ms=1_500)
    with pytest.raises(QuicSecurityCertificationError, match="address mismatch"):
        issuer.validate(token, address=("203.0.113.11", 4433), now_ms=1_050)


def test_quic_loss_recovery_evidence() -> None:
    evidence = quic_loss_recovery_evidence()

    assert set(evidence) == {
        "bytes_in_flight",
        "congestion_window",
        "lost_packets",
        "outstanding_packets",
        "pto_count",
        "rtt_observed",
    }
    assert evidence["rtt_observed"] is True
    assert evidence["congestion_window"] > 0
    assert json.dumps(evidence, sort_keys=True)


def test_quic_qlog_redaction() -> None:
    qlog = {
        "connection_id": "cid-secret",
        "events": [
            {"name": "packet_sent", "packet_number": 1, "retry_token": "secret-token"},
            {"name": "keys_updated", "secret": "traffic-secret"},
        ],
        "packet_number": 1,
    }

    redacted = redact_qlog(qlog)
    rendered = json.dumps(redacted, sort_keys=True)

    assert redacted["packet_number"] == 1
    assert "cid-secret" not in rendered
    assert "secret-token" not in rendered
    assert "traffic-secret" not in rendered
    assert rendered.count("[redacted]") == 3


def test_quic_anti_amplification_limit() -> None:
    blocked = anti_amplification_decision(
        bytes_received=1200,
        attempted_send_bytes=3601,
        address_validated=False,
    )
    allowed = anti_amplification_decision(
        bytes_received=1200,
        attempted_send_bytes=100_000,
        address_validated=True,
    )

    assert blocked["allowed"] is False
    assert blocked["limit_bytes"] == 3600
    assert blocked["reason"] == "anti_amplification_limit"
    assert allowed["allowed"] is True
    assert allowed["limit_bytes"] is None


def test_quic_spoofed_address_rejection() -> None:
    accepted = validate_source_address(
        expected_address=("198.51.100.1", 4433),
        observed_address=("198.51.100.1", 4433),
    )
    assert accepted["accepted"] is True

    with pytest.raises(QuicSecurityCertificationError, match="spoofed"):
        validate_source_address(
            expected_address=("198.51.100.1", 4433),
            observed_address=("198.51.100.99", 4433),
        )


def test_quic_path_validation_and_rebinding() -> None:
    pending = handle_path_validation_event(
        active_address=("203.0.113.10", 4433),
        observed_address=("203.0.113.10", 53000),
        challenge_response_valid=False,
    )
    validated = handle_path_validation_event(
        active_address=("203.0.113.10", 4433),
        observed_address=("203.0.113.10", 53000),
        challenge_response_valid=True,
    )
    disabled = handle_path_validation_event(
        active_address=("203.0.113.10", 4433),
        observed_address=("203.0.113.10", 53000),
        challenge_response_valid=True,
        migration_enabled=False,
    )

    assert pending["path_state"] == "pending_validation"
    assert pending["active_address"] == ["203.0.113.10", 4433]
    assert validated["path_state"] == "validated"
    assert validated["active_address"] == ["203.0.113.10", 53000]
    assert disabled["path_state"] == "rejected"


def test_quic_cid_rotation_observable() -> None:
    observation = observe_cid_rotation(
        old_cid=b"old-secret-cid",
        new_cid=b"new-secret-cid",
        sequence_number=7,
    )
    rendered = json.dumps(observation, sort_keys=True)

    assert observation["rotated"] is True
    assert observation["raw_cid_redacted"] is True
    assert observation["sequence_number"] == 7
    assert "old-secret-cid" not in rendered
    assert "new-secret-cid" not in rendered


def test_quic_retry_token_replay_rejected() -> None:
    issuer = QuicRetryTokenIssuer(secret=b"test-secret", lifetime_ms=100)
    token = issuer.issue(
        address=("203.0.113.10", 4433),
        original_destination_connection_id=b"odcid",
        issued_at_ms=1_000,
    )

    assert issuer.validate(token, address=("203.0.113.10", 4433), now_ms=1_050)["accepted"] is True
    with pytest.raises(QuicSecurityCertificationError, match="replay"):
        issuer.validate(token, address=("203.0.113.10", 4433), now_ms=1_060)


def test_quic_security_certification_fails_with_missing_qlog() -> None:
    with pytest.raises(QuicSecurityCertificationError, match="qlog"):
        certify_quic_operational_security(
            {
                "retry": {"accepted": True},
                "loss_recovery": quic_loss_recovery_evidence(),
            }
        )

    result = certify_quic_operational_security(
        {
            "retry": {"accepted": True},
            "loss_recovery": quic_loss_recovery_evidence(),
            "qlog": redact_qlog({"retry_token": "secret-token", "packet_number": 1}),
        }
    )
    assert result["certification_state"] == "certified"
