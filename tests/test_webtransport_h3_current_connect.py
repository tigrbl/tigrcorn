from tigrcorn_protocols.webtransport.profiles import CURRENT_PROFILE, draft13_profile


def test_current_connect_token_is_webtransport_h3() -> None:
    assert CURRENT_PROFILE.connect_token == b"webtransport-h3"


def test_draft13_connect_token_is_compatibility_only() -> None:
    assert draft13_profile().connect_token == b"webtransport"
    assert draft13_profile().connect_token != CURRENT_PROFILE.connect_token


def test_current_and_draft13_settings_are_disjoint_by_version_signal() -> None:
    current = CURRENT_PROFILE.settings_dict()
    draft13 = draft13_profile(8).settings_dict()
    assert set(current) != set(draft13)
