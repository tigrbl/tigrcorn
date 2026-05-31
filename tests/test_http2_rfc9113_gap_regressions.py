import pytest

from tigrcorn.config.defaults import default_config
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn.protocols.http2.state import H2StreamState


class _DummyReader:
    async def readexactly(self, n: int) -> bytes:
        raise EOFError


class _DummyWriter:
    def write(self, data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None


def _handler() -> HTTP2ConnectionHandler:
    async def app(scope, receive, send):
        return None

    return HTTP2ConnectionHandler(
        app=app,
        config=default_config(),
        access_logger=AccessLogger(configure_logging("warning"), enabled=False),
        reader=_DummyReader(),
        writer=_DummyWriter(),
        client=None,
        server=None,
        scheme="http",
    )


def _request_state(headers: list[tuple[bytes, bytes]], *, body: bytes = b"", end_stream: bool = True) -> H2StreamState:
    state = H2StreamState(1)
    state.headers = list(headers)
    state.headers_complete = True
    state.end_stream_received = end_stream
    if body:
        state.append_body(body)
    return state


def test_rfc9113_http2_rejects_content_length_mismatch() -> None:
    handler = _handler()
    state = _request_state(
        [
            (b":method", b"POST"),
            (b":path", b"/upload"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
            (b"content-length", b"3"),
        ],
        body=b"hello",
    )
    state.expected_content_length = handler._parse_content_length(state.headers)
    with pytest.raises(ProtocolError, match="content-length"):
        handler._build_request(state)


def test_rfc9113_http2_rejects_malformed_field_values() -> None:
    handler = _handler()
    state = _request_state(
        [
            (b":method", b"GET"),
            (b":path", b"/"),
            (b":scheme", b"http"),
            (b":authority", b"example"),
            (b"x-test", b" bad "),
        ]
    )
    with pytest.raises(ProtocolError, match="field value"):
        handler._build_request(state)


def test_rfc9113_http2_rejects_host_authority_mismatch() -> None:
    handler = _handler()
    state = _request_state(
        [
            (b":method", b"GET"),
            (b":path", b"/"),
            (b":scheme", b"http"),
            (b":authority", b"good.example"),
            (b"host", b"evil.example"),
        ]
    )
    with pytest.raises(ProtocolError, match="match :authority"):
        handler._build_request(state)


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        (
            [
                (b":method", b"GET"),
                (b":path", b""),
                (b":scheme", b"http"),
                (b":authority", b"example"),
            ],
            "empty :path",
        ),
        (
            [
                (b":method", b"GET"),
                (b":path", b"/"),
                (b":scheme", b"http"),
                (b":authority", b"user@example"),
            ],
            "userinfo",
        ),
    ],
)
def test_rfc9113_http2_rejects_malformed_request_targets(
    headers: list[tuple[bytes, bytes]],
    message: str,
) -> None:
    handler = _handler()
    state = _request_state(headers)
    with pytest.raises(ProtocolError, match=message):
        handler._build_request(state)


def test_rfc9113_http2_rejects_unsafe_server_push_methods() -> None:
    handler = _handler()
    state = H2StreamState(1)
    state.headers = [
        (b":method", b"GET"),
        (b":path", b"/"),
        (b":scheme", b"http"),
        (b":authority", b"example"),
    ]
    handler.streams.streams[1] = state
    with pytest.raises(ProtocolError, match="safe cacheable method"):
        handler._build_push_request(1, {"path": "/pushed", "method": "POST"})
