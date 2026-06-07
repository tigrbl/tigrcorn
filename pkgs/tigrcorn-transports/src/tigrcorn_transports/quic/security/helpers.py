from __future__ import annotations

import hashlib
import json
import time
from importlib import resources
from typing import Any, Mapping

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

_SENSITIVE_KEYS = ("connection_id", "secret", "token", "password", "private", "key")


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
        from .runtime import QuicSecurityCertificationError

        raise QuicSecurityCertificationError(f"unknown QUIC security profile: {profile}") from exc
    return json.loads(text)
