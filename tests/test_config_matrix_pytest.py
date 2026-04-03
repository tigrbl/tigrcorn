import pytest

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.config.validate import validate_config
from tigrcorn.errors import ConfigError


def test_tcp_defaults() -> None:
    config = build_config(host="127.0.0.1", port=1234, lifespan="off")
    listener = config.listeners[0]
    assert listener.kind == "tcp"
    assert "http1" in listener.enabled_protocols
    assert "websocket" in listener.enabled_protocols


def test_udp_http3_defaults() -> None:
    config = build_config(
        transport="udp",
        host="127.0.0.1",
        port=9443,
        lifespan="off",
        http_versions=["3"],
        protocols=["http3"],
    )
    listener = config.listeners[0]
    assert listener.kind == "udp"
    assert listener.scheme == "https"
    assert listener.enabled_protocols[:2] == ("quic", "http3")


def test_pipe_label() -> None:
    listener = ListenerConfig(kind="pipe", path="/tmp/tigrcorn.pipe")
    assert listener.label == "pipe:///tmp/tigrcorn.pipe"
    assert listener.enabled_protocols == ("rawframed",)


def test_udp_ssl_is_accepted_for_quic_tls() -> None:
    config = ServerConfig(
        listeners=[ListenerConfig(kind="udp", host="127.0.0.1", port=1, ssl_certfile="x", ssl_keyfile="y")]
    )
    validate_config(config)


def test_udp_client_auth_is_accepted_with_a_trust_store() -> None:
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind="udp",
                host="127.0.0.1",
                port=1,
                ssl_certfile="x",
                ssl_keyfile="y",
                ssl_ca_certs="ca.pem",
                ssl_require_client_cert=True,
            )
        ]
    )
    validate_config(config)


def test_udp_client_auth_requires_an_explicit_trust_store() -> None:
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind="udp",
                host="127.0.0.1",
                port=1,
                ssl_certfile="x",
                ssl_keyfile="y",
                ssl_require_client_cert=True,
            )
        ]
    )
    with pytest.raises(ConfigError):
        validate_config(config)


def test_tcp_client_auth_is_accepted_with_a_trust_store() -> None:
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind="tcp",
                host="127.0.0.1",
                port=1,
                ssl_certfile="x",
                ssl_keyfile="y",
                ssl_ca_certs="ca.pem",
                ssl_require_client_cert=True,
            )
        ]
    )
    validate_config(config)


def test_tcp_client_auth_requires_an_explicit_trust_store() -> None:
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind="tcp",
                host="127.0.0.1",
                port=1,
                ssl_certfile="x",
                ssl_keyfile="y",
                ssl_require_client_cert=True,
            )
        ]
    )
    with pytest.raises(ConfigError):
        validate_config(config)


def test_invalid_pipe_requires_path() -> None:
    config = ServerConfig(listeners=[ListenerConfig(kind="pipe", path=None)])
    with pytest.raises(ConfigError):
        validate_config(config)
