from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CapabilityState(str, Enum):
    COMPILED = "compiled"
    CONFIGURED = "configured"
    ENABLED = "enabled"
    CERTIFIED = "certified"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class UnsupportedCapabilityError(ValueError):
    """Raised when a required capability cannot be satisfied."""


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    id: str
    domain: str
    name: str
    compiled: bool
    certifiable: bool = False
    certified: bool = False
    optional: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    id: str
    domain: str
    name: str
    state: CapabilityState
    compiled: bool
    configured: bool
    enabled: bool
    certified: bool
    certifiable: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "name": self.name,
            "state": self.state.value,
            "compiled": self.compiled,
            "configured": self.configured,
            "enabled": self.enabled,
            "certified": self.certified,
            "certifiable": self.certifiable,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CapabilityExport:
    schema_version: str
    registry: str
    profile: str
    profile_valid: bool
    profile_errors: tuple[str, ...]
    capabilities: tuple[CapabilityRecord, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "registry": self.registry,
            "profile": self.profile,
            "profile_valid": self.profile_valid,
            "profile_errors": list(self.profile_errors),
            "capabilities": [record.as_dict() for record in self.capabilities],
        }
