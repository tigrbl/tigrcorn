from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

SETTING_ENABLE_CONNECT_PROTOCOL = 0x08
SETTING_H3_DATAGRAM = 0x33
SETTING_WT_ENABLED = 0x2C7CF000
SETTING_WT_MAX_SESSIONS = 0x14E9CD29


class WebTransportProfile(str, Enum):
    CURRENT = "current"
    DRAFT13 = "draft13"


@dataclass(frozen=True, slots=True)
class WebTransportProfileSpec:
    profile: WebTransportProfile
    connect_token: bytes
    settings: tuple[tuple[int, int], ...]
    requires_reset_stream_at: bool

    def settings_dict(self) -> dict[int, int]:
        return dict(self.settings)


CURRENT_PROFILE = WebTransportProfileSpec(
    profile=WebTransportProfile.CURRENT,
    connect_token=b"webtransport-h3",
    settings=(
        (SETTING_WT_ENABLED, 1),
        (SETTING_ENABLE_CONNECT_PROTOCOL, 1),
        (SETTING_H3_DATAGRAM, 1),
    ),
    requires_reset_stream_at=True,
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
    )


def profile_spec(value: str | WebTransportProfile, *, max_sessions: int = 1) -> WebTransportProfileSpec:
    profile = value if isinstance(value, WebTransportProfile) else WebTransportProfile(value)
    return CURRENT_PROFILE if profile is WebTransportProfile.CURRENT else draft13_profile(max_sessions)


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
    "SETTING_ENABLE_CONNECT_PROTOCOL",
    "SETTING_H3_DATAGRAM",
    "SETTING_WT_ENABLED",
    "SETTING_WT_MAX_SESSIONS",
    "WebTransportProfile",
    "WebTransportProfileSpec",
    "draft13_profile",
    "missing_peer_requirement",
    "profile_spec",
]
