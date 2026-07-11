from tigrcorn_protocols.webtransport.profiles import (
    SETTING_ENABLE_WEBTRANSPORT,
    SETTING_WT_ENABLED,
    SETTING_WT_MAX_SESSIONS,
    WebTransportSettingSemantics,
    profile_registry,
    profile_spec,
    resolve_profile_id,
)


def test_registry_keys_each_profile_by_stable_wire_identity() -> None:
    registry = profile_registry(max_sessions=17)
    assert tuple(registry) == ("draft02", "draft13", "ietf-current")
    assert registry["draft02"].setting_codepoint == SETTING_ENABLE_WEBTRANSPORT
    assert registry["draft13"].setting_codepoint == SETTING_WT_MAX_SESSIONS
    assert registry["ietf-current"].setting_codepoint == SETTING_WT_ENABLED
    assert len({spec.setting_codepoint for spec in registry.values()}) == len(registry)


def test_registry_captures_setting_semantics_and_codec_family() -> None:
    registry = profile_registry(max_sessions=17)
    assert registry["draft02"].setting_semantics is WebTransportSettingSemantics.BOOLEAN_ENABLEMENT
    assert registry["draft13"].setting_semantics is WebTransportSettingSemantics.MAX_SESSIONS
    assert registry["draft13"].settings_dict()[SETTING_WT_MAX_SESSIONS] == 17
    assert {spec.codec_family for spec in registry.values()} == {"draft02", "draft13", "ietf-current"}


def test_aliases_resolve_without_becoming_registry_entries() -> None:
    assert resolve_profile_id("current") == "ietf-current"
    assert resolve_profile_id("chromium") == "draft02"
    assert profile_spec("current") is profile_spec("ietf-current")
    assert "current" not in profile_registry()
    assert "chromium" not in profile_registry()


def test_draft02_is_registered_but_not_yet_advertisable() -> None:
    spec = profile_registry()["draft02"]
    assert spec.connect_token == b"webtransport"
    assert spec.implemented is False
