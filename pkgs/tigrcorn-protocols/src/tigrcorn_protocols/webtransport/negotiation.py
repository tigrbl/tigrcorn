from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .profiles import (
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_H3_DATAGRAM,
    WebTransportProfileSpec,
    WebTransportSettingSemantics,
    profile_registry,
)


@dataclass(frozen=True, slots=True)
class WebTransportNegotiationResult:
    configured_profiles: tuple[str, ...]
    advertised_codepoints: tuple[int, ...]
    peer_profiles: tuple[str, ...]
    mutual_profiles: tuple[str, ...]
    preferred_profile: str
    selected_profile: str | None
    failure_reason: str | None = None


def settings_for_profiles(
    profile_ids: Sequence[str],
    *,
    max_sessions: int = 1,
) -> dict[int, int]:
    registry = profile_registry(max_sessions=max_sessions)
    settings = {
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
    }
    for profile_id in profile_ids:
        spec = registry[profile_id]
        if not spec.implemented:
            raise ValueError(f"WebTransport profile is not implemented: {profile_id}")
        settings[spec.setting_codepoint] = spec.settings_dict()[spec.setting_codepoint]
    return settings


def peer_profiles_from_settings(
    settings: Mapping[int, int],
    *,
    max_sessions: int = 1,
) -> tuple[tuple[str, ...], str | None]:
    supported: list[str] = []
    for profile_id, spec in profile_registry(max_sessions=max_sessions).items():
        if spec.setting_codepoint not in settings:
            continue
        value = int(settings[spec.setting_codepoint])
        valid = (
            value == 1
            if spec.setting_semantics is WebTransportSettingSemantics.BOOLEAN_ENABLEMENT
            else value > 0
        )
        if not valid:
            return (), f"malformed-setting:{spec.setting_codepoint:#x}"
        supported.append(profile_id)
    return tuple(supported), None


def negotiate_profiles(
    configured_profiles: Sequence[str],
    preferred_profile: str,
    peer_settings: Mapping[int, int],
    *,
    max_sessions: int = 1,
) -> WebTransportNegotiationResult:
    configured = tuple(dict.fromkeys(configured_profiles))
    registry = profile_registry(max_sessions=max_sessions)
    advertised = tuple(registry[name].setting_codepoint for name in configured)
    peer, failure = peer_profiles_from_settings(peer_settings, max_sessions=max_sessions)
    mutual = tuple(name for name in configured if name in peer)
    selected = preferred_profile if preferred_profile in mutual else (mutual[0] if mutual else None)
    if failure is None and selected is None:
        failure = "no-mutual-profile"
    return WebTransportNegotiationResult(
        configured_profiles=configured,
        advertised_codepoints=advertised,
        peer_profiles=peer,
        mutual_profiles=mutual,
        preferred_profile=preferred_profile,
        selected_profile=selected,
        failure_reason=failure,
    )


def selected_profile_spec(
    result: WebTransportNegotiationResult,
    *,
    max_sessions: int = 1,
) -> WebTransportProfileSpec | None:
    if result.selected_profile is None:
        return None
    return profile_registry(max_sessions=max_sessions)[result.selected_profile]


__all__ = [
    "WebTransportNegotiationResult",
    "negotiate_profiles",
    "peer_profiles_from_settings",
    "selected_profile_spec",
    "settings_for_profiles",
]
