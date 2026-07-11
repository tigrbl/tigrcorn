from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

SETTING_ENABLE_CONNECT_PROTOCOL = 0x08
SETTING_H3_DATAGRAM = 0x33
SETTING_ENABLE_WEBTRANSPORT = 0x2B603742
SETTING_WT_ENABLED = 0x2C7CF000
SETTING_WT_MAX_SESSIONS = 0x14E9CD29


class WebTransportProfile(str, Enum):
    DRAFT02 = "draft02"
    DRAFT13 = "draft13"
    IETF_CURRENT = "ietf-current"
    CURRENT = "ietf-current"


class WebTransportSettingSemantics(str, Enum):
    BOOLEAN_ENABLEMENT = "boolean-enablement"
    MAX_SESSIONS = "max-sessions"


@dataclass(frozen=True, slots=True)
class WebTransportProfileSpec:
    profile: WebTransportProfile
    connect_token: bytes
    settings: tuple[tuple[int, int], ...]
    requires_reset_stream_at: bool
    setting_codepoint: int
    setting_semantics: WebTransportSettingSemantics
    codec_family: str
    implemented: bool = True

    def settings_dict(self) -> dict[int, int]:
        return dict(self.settings)


CURRENT_PROFILE = WebTransportProfileSpec(
    profile=WebTransportProfile.IETF_CURRENT,
    connect_token=b"webtransport-h3",
    settings=(
        (SETTING_WT_ENABLED, 1),
        (SETTING_ENABLE_CONNECT_PROTOCOL, 1),
        (SETTING_H3_DATAGRAM, 1),
    ),
    requires_reset_stream_at=True,
    setting_codepoint=SETTING_WT_ENABLED,
    setting_semantics=WebTransportSettingSemantics.BOOLEAN_ENABLEMENT,
    codec_family="ietf-current",
)

DRAFT02_PROFILE = WebTransportProfileSpec(
    profile=WebTransportProfile.DRAFT02,
    connect_token=b"webtransport",
    settings=(
        (SETTING_ENABLE_WEBTRANSPORT, 1),
        (SETTING_ENABLE_CONNECT_PROTOCOL, 1),
        (SETTING_H3_DATAGRAM, 1),
    ),
    requires_reset_stream_at=False,
    setting_codepoint=SETTING_ENABLE_WEBTRANSPORT,
    setting_semantics=WebTransportSettingSemantics.BOOLEAN_ENABLEMENT,
    codec_family="draft02",
    implemented=False,
)


def draft13_profile(max_sessions: int = 1) -> WebTransportProfileSpec:
    return WebTransportProfileSpec(
        profile=WebTransportProfile.DRAFT13,
        connect_token=b"webtransport",
        settings=(
            (SETTING_WT_MAX_SESSIONS, max(1, int(max_sessions))),
            (SETTING_ENABLE_CONNECT_PROTOCOL, 1),
            (SETTING_H3_DATAGRAM, 1),
        ),
        requires_reset_stream_at=False,
        setting_codepoint=SETTING_WT_MAX_SESSIONS,
        setting_semantics=WebTransportSettingSemantics.MAX_SESSIONS,
        codec_family="draft13",
    )


PROFILE_ALIASES = {
    "current": WebTransportProfile.IETF_CURRENT.value,
    "chromium": WebTransportProfile.DRAFT02.value,
}


def resolve_profile_id(value: str | WebTransportProfile) -> str:
    raw = value.value if isinstance(value, WebTransportProfile) else str(value)
    normalized = raw.strip().lower()
    return PROFILE_ALIASES.get(normalized, normalized)


def profile_registry(*, max_sessions: int = 1) -> dict[str, WebTransportProfileSpec]:
    return {
        WebTransportProfile.DRAFT02.value: DRAFT02_PROFILE,
        WebTransportProfile.DRAFT13.value: draft13_profile(max_sessions),
        WebTransportProfile.IETF_CURRENT.value: CURRENT_PROFILE,
    }


def profile_spec(value: str | WebTransportProfile, *, max_sessions: int = 1) -> WebTransportProfileSpec:
    profile_id = resolve_profile_id(value)
    try:
        return profile_registry(max_sessions=max_sessions)[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown WebTransport profile: {value!r}") from exc


def missing_peer_requirement(
    spec: WebTransportProfileSpec,
    settings: Mapping[int, int],
    *,
    max_datagram_frame_size: int | None,
    reset_stream_at: bool,
) -> str | None:
    for setting_id, expected in spec.settings:
        if int(settings.get(setting_id, 0)) != expected and setting_id != SETTING_ENABLE_CONNECT_PROTOCOL:
            return f"setting:{setting_id:#x}"
    if not max_datagram_frame_size:
        return "quic:max_datagram_frame_size"
    if spec.requires_reset_stream_at and not reset_stream_at:
        return "quic:reset_stream_at"
    return None


__all__ = [
    "CURRENT_PROFILE",
    "DRAFT02_PROFILE",
    "PROFILE_ALIASES",
    "SETTING_ENABLE_CONNECT_PROTOCOL",
    "SETTING_ENABLE_WEBTRANSPORT",
    "SETTING_H3_DATAGRAM",
    "SETTING_WT_ENABLED",
    "SETTING_WT_MAX_SESSIONS",
    "WebTransportProfile",
    "WebTransportProfileSpec",
    "WebTransportSettingSemantics",
    "draft13_profile",
    "missing_peer_requirement",
    "profile_spec",
    "profile_registry",
    "resolve_profile_id",
]
