import pytest

from tigrcorn.cli import build_parser
from tigrcorn_config.load import build_config, build_config_from_namespace, build_config_from_sources
from tigrcorn_core.errors import ConfigError


def test_default_and_legacy_compatibility_map_to_concrete_profiles() -> None:
    assert build_config().webtransport.profiles == ["ietf-current"]
    legacy = build_config(config={"webtransport": {"compatibility": "draft13"}})
    assert legacy.webtransport.profiles == ["draft13"]
    assert legacy.webtransport.preferred_profile == "draft13"


def test_multiple_implemented_profiles_and_preference_are_accepted() -> None:
    config = build_config(
        webtransport_profiles=["draft13", "current"],
        webtransport_preferred_profile="current",
    )
    assert config.webtransport.profiles == ["draft13", "ietf-current"]
    assert config.webtransport.preferred_profile == "ietf-current"
    assert config.webtransport.compatibility == "current"


def test_unknown_or_unselected_preferred_profile_fails_startup() -> None:
    with pytest.raises(ConfigError, match="unsupported WebTransport profiles"):
        build_config(webtransport_profiles=["unknown"])
    with pytest.raises(ConfigError, match="preferred_profile must be included"):
        build_config(
            webtransport_profiles=["draft13"],
            webtransport_preferred_profile="current",
        )


def test_chromium_alias_fails_until_draft02_codec_is_implemented() -> None:
    with pytest.raises(ConfigError, match="not implemented: draft02"):
        build_config(webtransport_profiles=["chromium"])


def test_mapping_surface_accepts_profiles_and_preference() -> None:
    config = build_config(
        config={
            "webtransport": {
                "profiles": ["ietf-current", "draft13"],
                "preferred_profile": "draft13",
            }
        }
    )
    assert config.webtransport.profiles == ["ietf-current", "draft13"]
    assert config.webtransport.preferred_profile == "draft13"
    assert config.webtransport.compatibility == "draft13"


def test_cli_surface_accepts_repeated_profiles() -> None:
    namespace = build_parser().parse_args(
        [
            "tests.fixtures_pkg.appmod:app",
            "--webtransport-profile",
            "draft13",
            "--webtransport-profile",
            "current",
            "--webtransport-preferred-profile",
            "draft13",
        ]
    )
    config = build_config_from_namespace(namespace)
    assert config.webtransport.profiles == ["draft13", "ietf-current"]
    assert config.webtransport.preferred_profile == "draft13"


def test_environment_surface_accepts_profile_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WT_WEBTRANSPORT_PROFILES", "ietf-current,draft13")
    monkeypatch.setenv("WT_WEBTRANSPORT_PREFERRED_PROFILE", "draft13")
    config = build_config_from_sources(env_prefix="WT")
    assert config.webtransport.profiles == ["ietf-current", "draft13"]
    assert config.webtransport.preferred_profile == "draft13"
