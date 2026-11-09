from tigrcorn_protocols.webtransport.profiles import (
    CURRENT_PROFILE,
    WebTransportProfile,
    draft13_profile,
    missing_peer_requirement,
    profile_spec,
)


def test_profile_selection_defaults_are_explicit() -> None:
    assert profile_spec("current") is CURRENT_PROFILE
    assert profile_spec(WebTransportProfile.DRAFT13).profile is WebTransportProfile.DRAFT13


def test_current_profile_requires_peer_quic_capabilities() -> None:
    settings = CURRENT_PROFILE.settings_dict()
    assert missing_peer_requirement(
        CURRENT_PROFILE,
        settings,
        max_datagram_frame_size=1200,
        reset_stream_at=True,
    ) is None
    assert missing_peer_requirement(
        CURRENT_PROFILE,
        settings,
        max_datagram_frame_size=1200,
        reset_stream_at=False,
    ) == "quic:reset_stream_at"


def test_draft13_profile_does_not_accept_current_token() -> None:
    assert draft13_profile().connect_token != CURRENT_PROFILE.connect_token


def test_missing_profile_setting_is_reported_stably() -> None:
    requirement = missing_peer_requirement(
        CURRENT_PROFILE,
        {},
        max_datagram_frame_size=1200,
        reset_stream_at=True,
    )
    assert requirement and requirement.startswith("setting:0x")
