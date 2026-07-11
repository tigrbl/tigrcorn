from tigrcorn_config.load.mapping import config_from_mapping
from tigrcorn.protocols.http3.codec import (
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_H3_DATAGRAM,
    SETTING_WT_ENABLED,
    SETTING_WT_MAX_SESSIONS,
)
from tigrcorn_protocols.webtransport.profiles import CURRENT_PROFILE


def test_webtransport_default_profile_atomic_enable() -> None:
    config = config_from_mapping({
        "listeners": [{"kind": "udp", "http_versions": ["3"], "protocols": ["webtransport"]}],
        "webtransport": {"enabled": True},
    })
    assert config.webtransport.enabled is True
    assert config.webtransport.compatibility == "current"
    assert config.listeners[0].enabled_protocols == ("quic", "http3", "webtransport")


def test_webtransport_default_profile_settings_are_current() -> None:
    settings = CURRENT_PROFILE.settings_dict()
    assert settings == {
        SETTING_WT_ENABLED: 1,
        SETTING_ENABLE_CONNECT_PROTOCOL: 1,
        SETTING_H3_DATAGRAM: 1,
    }
    assert SETTING_WT_MAX_SESSIONS not in settings


def test_webtransport_disabled_does_not_add_listener_protocol() -> None:
    config = config_from_mapping({"listeners": [{"kind": "udp", "http_versions": ["3"]}]})
    assert "webtransport" not in config.listeners[0].enabled_protocols


def test_webtransport_max_sessions_remains_local_governance() -> None:
    config = config_from_mapping({"webtransport": {"max_sessions": 7}})
    assert config.webtransport.max_sessions == 7
    assert SETTING_WT_MAX_SESSIONS not in CURRENT_PROFILE.settings_dict()
