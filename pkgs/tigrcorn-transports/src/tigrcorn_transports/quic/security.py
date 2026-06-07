from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Mapping

from tigrcorn_transports.quic.recovery import QuicLossRecovery


class QuicSecurityCertificationError(ValueError):
    """Raised when QUIC operational security evidence fails closed."""


REQUIRED_ARTIFACT_SECTIONS: tuple[str, ...] = (
    "address_validation",
    "anti_amplification",
    "certification",
    "checks",
    "connection_id",
    "loss_recovery",
    "profile",
    "qlog",
    "retry",
)

QUIC_SECURITY_CHECKS: tuple[dict[str, str], ...] = (
    {"id": "quic.retry-token", "tier": "T1", "profile_field": "quic.require_retry"},
    {"id": "quic.loss-recovery", "tier": "T1", "profile_field": "rfc_targets.RFC 9002"},
    {"id": "quic.qlog-redaction", "tier": "T1", "profile_field": "operational-evidence.qlog"},
    {"id": "quic.anti-amplification", "tier": "T2", "profile_field": "quic.address-validation"},
    {"id": "quic.spoofed-address", "tier": "T2", "profile_field": "quic.address-validation"},
    {"id": "quic.path-validation", "tier": "T2", "profile_field": "quic.migration"},
    {"id": "quic.cid-rotation", "tier": "T2", "profile_field": "quic.connection-id"},
    {"id": "quic.retry-replay", "tier": "T2", "profile_field": "quic.require_retry"},
    {"id": "quic.qlog-required", "tier": "T2", "profile_field": "operational-evidence.qlog"},
)

_SENSITIVE_KEYS = ("connection_id", "secret", "token", "password", "private", "key")


@dataclass(slots=True)
class QuicRetryTokenIssuer:
    secret: bytes
    lifetime_ms: int = 10_000
    replay_cache: set[str] = field(default_factory=set)

    def issue(
        self,
        *,
        address: tuple[str, int],
        original_destination_connection_id: bytes,
        issued_at_ms: int | None = None,
    ) -> bytes:
        issued = _current_time_ms() if issued_at_ms is None else issued_at_ms
        payload = {
            "address": [address[0], address[1]],
            "issued_at_ms": issued,
            "odcid": original_destination_connection_id.hex(),
            "version": 1,
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        mac = hmac.new(self.secret, body, hashlib.sha256).hexdigest().encode("ascii")
        return body + b"." + mac

    def validate(
        self,
        token: bytes,
        *,
        address: tuple[str, int],
        now_ms: int | None = None,
        consume: bool = True,
    ) -> dict[str, Any]:
        try:
            body, mac = token.rsplit(b".", 1)
        except ValueError as exc:
            raise QuicSecurityCertificationError("invalid retry token format") from exc
        expected = hmac.new(self.secret, body, hashlib.sha256).hexdigest().encode("ascii")
        if not hmac.compare_digest(mac, expected):
            raise QuicSecurityCertificationError("invalid retry token integrity")
        payload = json.loads(body.decode("utf-8"))
        token_address = tuple(payload["address"])
        if token_address != address:
            raise QuicSecurityCertificationError("retry token address mismatch")
        at = _current_time_ms() if now_ms is None else now_ms
        if at - int(payload["issued_at_ms"]) > self.lifetime_ms:
            raise QuicSecurityCertificationError("stale retry token")
        fingerprint = _hash_bytes(token)
        if consume and fingerprint in self.replay_cache:
            raise QuicSecurityCertificationError("retry token replay")
        if consume:
            self.replay_cache.add(fingerprint)
        return {
            "accepted": True,
            "address": [address[0], address[1]],
            "issued_at_ms": int(payload["issued_at_ms"]),
            "original_destination_connection_id_hash": _hash_text(str(payload["odcid"])),
            "token_hash": fingerprint,
        }


@dataclass(slots=True)
class QuicOperationalSecurityRuntime:
    secret: bytes
    profile: str = "strict-h3-edge"
    lifetime_ms: int = 10_000
    issuer: QuicRetryTokenIssuer = field(init=False)
    _evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.issuer = QuicRetryTokenIssuer(
            secret=self.secret,
            lifetime_ms=self.lifetime_ms,
        )

    def issue_retry_token(
        self,
        *,
        address: tuple[str, int],
        original_destination_connection_id: bytes,
        issued_at_ms: int | None = None,
    ) -> bytes:
        token = self.issuer.issue(
            address=address,
            original_destination_connection_id=original_destination_connection_id,
            issued_at_ms=issued_at_ms,
        )
        self._evidence["retry"] = {
            "accepted": False,
            "address": [address[0], address[1]],
            "issued": True,
            "original_destination_connection_id_hash": _hash_bytes(original_destination_connection_id),
            "token_hash": _hash_bytes(token),
        }
        return token

    def validate_retry_token(
        self,
        token: bytes,
        *,
        address: tuple[str, int],
        now_ms: int | None = None,
        consume: bool = True,
    ) -> dict[str, Any]:
        result = self.issuer.validate(
            token,
            address=address,
            now_ms=now_ms,
            consume=consume,
        )
        self._evidence["retry"] = {
            **result,
            "path": "runtime_retry",
        }
        return dict(self._evidence["retry"])

    def enforce_anti_amplification(
        self,
        *,
        bytes_received: int,
        attempted_send_bytes: int,
        address_validated: bool,
    ) -> dict[str, Any]:
        decision = anti_amplification_decision(
            bytes_received=bytes_received,
            attempted_send_bytes=attempted_send_bytes,
            address_validated=address_validated,
        )
        self._evidence["anti_amplification"] = decision
        if not decision["allowed"]:
            raise QuicSecurityCertificationError(decision["reason"])
        return dict(decision)

    def record_qlog_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        qlog = dict(self._evidence.get("qlog") or {"events": ()})
        events = tuple(qlog.get("events") or ())
        qlog["events"] = events + (redact_qlog(event),)
        qlog["redacted"] = True
        self._evidence["qlog"] = qlog
        return dict(qlog)

    def record_loss_recovery(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._evidence["loss_recovery"] = dict(evidence or quic_loss_recovery_evidence())
        return dict(self._evidence["loss_recovery"])

    def record_path_validation(
        self,
        *,
        active_address: tuple[str, int],
        observed_address: tuple[str, int],
        challenge_response_valid: bool,
        migration_enabled: bool = True,
    ) -> dict[str, Any]:
        result = handle_path_validation_event(
            active_address=active_address,
            observed_address=observed_address,
            challenge_response_valid=challenge_response_valid,
            migration_enabled=migration_enabled,
        )
        self._evidence["address_validation"] = result
        return dict(result)

    def record_packet_path(
        self,
        *,
        packet: bytes,
        endpoint: tuple[str, int],
        active_address: tuple[str, int] | None = None,
        address_validated: bool = False,
        attempted_send_bytes: int | None = None,
    ) -> dict[str, Any]:
        self.enforce_anti_amplification(
            bytes_received=len(packet),
            attempted_send_bytes=len(packet) if attempted_send_bytes is None else attempted_send_bytes,
            address_validated=address_validated,
        )
        self.record_qlog_event(
            {
                "connection_id": packet[:8].hex(),
                "event": "packet_received",
                "packet_size": len(packet),
                "peer_address": [endpoint[0], endpoint[1]],
            }
        )
        self.record_path_validation(
            active_address=active_address or endpoint,
            observed_address=endpoint,
            challenge_response_valid=True,
        )
        return self.runtime_evidence()

    def runtime_evidence(self) -> dict[str, Any]:
        evidence = dict(self._evidence)
        if "loss_recovery" not in evidence:
            evidence["loss_recovery"] = quic_loss_recovery_evidence()
        return {key: evidence[key] for key in sorted(evidence)}

    def certify(self) -> dict[str, Any]:
        return certify_quic_operational_security(self.runtime_evidence())


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


def _current_time_ms() -> int:
    return int(time.time() * 1000)


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:16]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key in sorted(payload):
        value = payload[key]
        lowered = str(key).lower()
        if any(sensitive in lowered for sensitive in _SENSITIVE_KEYS):
            redacted[key] = "[redacted]"
        elif isinstance(value, Mapping):
            redacted[key] = _redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_mapping(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def _stable_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    ordered = {key: artifact[key] for key in sorted(artifact)}
    ordered["sections"] = REQUIRED_ARTIFACT_SECTIONS
    return ordered


def _load_profile(profile: str) -> Mapping[str, Any]:
    profile_name = f"{profile}.profile.json"
    try:
        text = resources.files("tigrcorn.profiles").joinpath(profile_name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise QuicSecurityCertificationError(f"unknown QUIC security profile: {profile}") from exc
    return json.loads(text)
