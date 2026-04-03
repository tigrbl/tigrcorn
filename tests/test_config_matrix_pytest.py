from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.config.validate import validate_config
from tigrcorn.errors import ConfigError


def test_partial_server_config_normalizes_http2_defaults():
    config = ServerConfig()
    validate_config(config)
    assert config.http.http2_max_concurrent_streams == 128
    assert config.http.http2_max_headers_size == config.http.max_header_size
    assert config.http.http2_max_frame_size == 16_384


def test_udp_client_auth_requires_explicit_trust_store():
    config = ServerConfig(
        listeners=[
            ListenerConfig(
                kind='udp',
                host='127.0.0.1',
                port=1,
                ssl_certfile='x',
                ssl_keyfile='y',
                ssl_require_client_cert=True,
            )
        ]
    )
    try:
        validate_config(config)
    except ConfigError:
        return
    raise AssertionError('expected ConfigError when udp client auth omits ssl_ca_certs')
