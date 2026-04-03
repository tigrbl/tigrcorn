from tigrcorn.compat.conformance import compare_sequence, normalize_scope
from tigrcorn.compat.hypercorn import HYPERCORN_COMPAT
from tigrcorn.compat.uvicorn import UVICORN_COMPAT
from tigrcorn.config.model import ListenerConfig
from tigrcorn.security.alpn import normalize_alpn
from tigrcorn.security.certs import PeerCertificate
from tigrcorn.security.policies import TLSPolicy
from tigrcorn.security.tls import build_server_ssl_context
from tigrcorn.utils.ids import next_id, next_session_id, next_stream_id


def test_alpn_and_policy() -> None:
    assert normalize_alpn("h2") == "h2"
    assert normalize_alpn("") is None
    cert = PeerCertificate(serial_number="abc")
    assert cert.serial_number == "abc"
    policy = TLSPolicy(require_client_cert=True)
    assert policy.require_client_cert
    assert build_server_ssl_context(ListenerConfig()) is None


def test_compat_profiles_and_conformance() -> None:
    assert UVICORN_COMPAT.http1
    assert HYPERCORN_COMPAT.http2
    left = [{"type": "http.response.start", "headers": [(b"a", b"b")]}]
    right = [{"type": "http.response.start", "headers": [(b"a", b"b")]}]
    diff = compare_sequence(left, right)
    assert diff.ok
    assert "state" not in normalize_scope({"type": "http", "state": {}})


def test_ids_monotonic() -> None:
    a, b = next_id(), next_id()
    assert a < b
    assert next_session_id() < next_session_id()
    assert next_stream_id() < next_stream_id()
