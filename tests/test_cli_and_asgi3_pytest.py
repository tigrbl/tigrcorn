from tigrcorn.cli import build_parser
from tigrcorn.compat.asgi3 import assert_asgi3_app, describe_app, is_http_event, is_http_scope, is_lifespan_scope, is_websocket_scope


def test_parser() -> None:
    parser = build_parser()
    ns = parser.parse_args([
        "tests.fixtures_pkg.appmod:app",
        "--transport", "udp",
        "--protocol", "http3",
        "--http", "3",
        "--ssl-ca-certs", "ca.pem",
        "--ssl-require-client-cert",
    ])
    assert ns.transport == "udp"
    assert ns.protocols == ["http3"]
    assert ns.http_versions == ["3"]
    assert ns.ssl_ca_certs == "ca.pem"
    assert ns.ssl_require_client_cert


def test_asgi3_helpers() -> None:
    async def app(scope, receive, send):
        return None

    info = describe_app(app)
    assert info.parameter_count == 3
    assert_asgi3_app(app)
    assert is_http_scope({"type": "http"})
    assert is_websocket_scope({"type": "websocket"})
    assert is_lifespan_scope({"type": "lifespan"})
    assert is_http_event({"type": "http.request"})
