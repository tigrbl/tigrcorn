from __future__ import annotations

from typing import Any, Mapping

from tigrcorn_transports.quic.recovery import QuicLossRecovery
from .helpers import _current_time_ms, _hash_bytes, _hash_text, _load_profile, _redact_mapping, _stable_artifact
from .runtime import QUIC_SECURITY_CHECKS, QuicSecurityCertificationError

def quic_security_checks(profile: str = "strict-h3-edge") -> dict[str, Any]:
    profile_data = _load_profile(profile)
    profile_quic = profile_data.get("effective_config", {}).get("quic", {})
    rfc_targets = tuple(profile_data.get("rfc_targets", ()))
    return {
        "checks": tuple(dict(check) for check in QUIC_SECURITY_CHECKS),
        "profile": profile,
        "profile_quic": {
            "early_data_policy": profile_quic.get("early_data_policy"),
            "max_datagram_size": profile_quic.get("max_datagram_size"),
            "require_retry": bool(profile_quic.get("require_retry")),
        },
        "rfc_targets": rfc_targets,
    }


def quic_security_certification_artifact(profile: str = "strict-h3-edge") -> dict[str, Any]:
    checks = quic_security_checks(profile)
    artifact = {
        "address_validation": {
            "path_validation": "required",
            "spoofed_source_policy": "fail_closed",
        },
        "anti_amplification": anti_amplification_decision(
            bytes_received=1200,
            attempted_send_bytes=3600,
            address_validated=False,
        ),
        "artifact_id": "tigrcorn.quic.operational-security",
        "certification": {
            "state": "uncertified",
            "required_evidence": ("retry", "loss_recovery", "qlog"),
        },
        "checks": checks["checks"],
        "connection_id": observe_cid_rotation(
            old_cid=b"old-cid-1",
            new_cid=b"new-cid-2",
            sequence_number=1,
        ),
        "loss_recovery": quic_loss_recovery_evidence(),
        "profile": {
            "id": profile,
            "quic": checks["profile_quic"],
            "rfc_targets": checks["rfc_targets"],
        },
        "qlog": redact_qlog(
            {
                "event": "packet_sent",
                "connection_id": "cid-secret",
                "retry_token": "retry-token-secret",
                "packet_number": 1,
            }
        ),
        "retry": {
            "accept_reject": "validated",
            "replay_policy": "single_use_or_bounded",
        },
        "schema_version": 1,
    }
    return _stable_artifact(artifact)


def anti_amplification_decision(
    *,
    bytes_received: int,
    attempted_send_bytes: int,
    address_validated: bool,
) -> dict[str, Any]:
    if bytes_received < 0 or attempted_send_bytes < 0:
        raise QuicSecurityCertificationError("anti-amplification counters must be non-negative")
    limit = None if address_validated else bytes_received * 3
    allowed = address_validated or attempted_send_bytes <= int(limit or 0)
    return {
        "address_validated": address_validated,
        "allowed": allowed,
        "attempted_send_bytes": attempted_send_bytes,
        "bytes_received": bytes_received,
        "limit_bytes": limit,
        "reason": "address_validated" if address_validated else ("within_limit" if allowed else "anti_amplification_limit"),
    }


def validate_source_address(
    *,
    expected_address: tuple[str, int],
    observed_address: tuple[str, int],
) -> dict[str, Any]:
    if expected_address != observed_address:
        raise QuicSecurityCertificationError("spoofed QUIC source address rejected")
    return {
        "address": [observed_address[0], observed_address[1]],
        "accepted": True,
    }


def handle_path_validation_event(
    *,
    active_address: tuple[str, int],
    observed_address: tuple[str, int],
    challenge_response_valid: bool,
    migration_enabled: bool = True,
) -> dict[str, Any]:
    if active_address == observed_address:
        return {
            "active_address": [active_address[0], active_address[1]],
            "new_address": None,
            "path_state": "unchanged",
            "requires_validation": False,
        }
    if not migration_enabled:
        return {
            "active_address": [active_address[0], active_address[1]],
            "new_address": [observed_address[0], observed_address[1]],
            "path_state": "rejected",
            "requires_validation": True,
        }
    return {
        "active_address": [observed_address[0], observed_address[1]] if challenge_response_valid else [active_address[0], active_address[1]],
        "new_address": [observed_address[0], observed_address[1]],
        "path_state": "validated" if challenge_response_valid else "pending_validation",
        "requires_validation": True,
    }


def observe_cid_rotation(
    *,
    old_cid: bytes,
    new_cid: bytes,
    sequence_number: int,
) -> dict[str, Any]:
    if sequence_number < 0:
        raise QuicSecurityCertificationError("CID sequence number must be non-negative")
    return {
        "new_cid_hash": _hash_bytes(new_cid),
        "old_cid_hash": _hash_bytes(old_cid),
        "raw_cid_redacted": True,
        "rotated": old_cid != new_cid,
        "sequence_number": sequence_number,
    }


def quic_loss_recovery_evidence() -> dict[str, Any]:
    recovery = QuicLossRecovery(max_datagram_size=1200)
    recovery.on_packet_sent(1, 1200, packet_space="application", sent_time=1.0)
    recovery.on_packet_sent(2, 1200, packet_space="application", sent_time=1.1)
    recovery.on_packet_sent(3, 1200, packet_space="application", sent_time=1.2)
    lost = recovery.on_ack_received([3], packet_space="application", now=2.0)
    snapshot = recovery.snapshot()
    return {
        "bytes_in_flight": snapshot.bytes_in_flight,
        "congestion_window": snapshot.congestion_window,
        "lost_packets": tuple(lost),
        "outstanding_packets": snapshot.outstanding_packets,
        "pto_count": snapshot.pto_count,
        "rtt_observed": snapshot.latest_rtt > 0,
    }


def redact_qlog(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _redact_mapping(payload)


def certify_quic_operational_security(evidence: Mapping[str, Any]) -> dict[str, Any]:
    required = ("retry", "loss_recovery", "qlog")
    missing = tuple(key for key in required if not evidence.get(key))
    if missing:
        raise QuicSecurityCertificationError(
            "missing QUIC operational evidence: " + ", ".join(missing)
        )
    return {
        "certification_state": "certified",
        "evidence_keys": tuple(sorted(evidence)),
        "required_evidence": required,
    }


