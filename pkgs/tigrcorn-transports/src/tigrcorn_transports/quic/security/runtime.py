from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from .helpers import _current_time_ms, _hash_bytes, _hash_text, _redact_mapping, _stable_artifact

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
        from .certification import anti_amplification_decision

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
        from .certification import redact_qlog

        qlog = dict(self._evidence.get("qlog") or {"events": ()})
        events = tuple(qlog.get("events") or ())
        qlog["events"] = events + (redact_qlog(event),)
        qlog["redacted"] = True
        self._evidence["qlog"] = qlog
        return dict(qlog)

    def record_loss_recovery(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        from .certification import quic_loss_recovery_evidence

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
        from .certification import handle_path_validation_event

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
        from .certification import quic_loss_recovery_evidence

        evidence = dict(self._evidence)
        if "loss_recovery" not in evidence:
            evidence["loss_recovery"] = quic_loss_recovery_evidence()
        return {key: evidence[key] for key in sorted(evidence)}

    def certify(self) -> dict[str, Any]:
        from .certification import certify_quic_operational_security

        return certify_quic_operational_security(self.runtime_evidence())

