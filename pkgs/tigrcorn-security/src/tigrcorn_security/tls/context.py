from __future__ import annotations

from .imports import *
from .models import *

def build_server_ssl_context(listener: ListenerConfig) -> ServerTLSContext | None:
    if not listener.ssl_enabled:
        return None
    assert listener.ssl_certfile is not None
    assert listener.ssl_keyfile is not None
    certificate_pem = Path(listener.ssl_certfile).read_bytes()
    private_key_pem = Path(listener.ssl_keyfile).read_bytes()
    private_key_password = getattr(listener, 'ssl_keyfile_password', None)
    if private_key_password is not None and not isinstance(private_key_password, bytes):
        private_key_password = str(private_key_password).encode('utf-8')
    trusted = (Path(listener.ssl_ca_certs).read_bytes(),) if listener.ssl_ca_certs else ()
    validation_policy = build_validation_policy_for_listener(listener)
    server_name = _listener_server_name(listener)
    return ServerTLSContext(
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
        private_key_password=private_key_password,
        trusted_certificates=trusted,
        alpn_protocols=tuple(listener.alpn_protocols),
        require_client_certificate=listener.ssl_require_client_cert,
        validation_policy=validation_policy,
        cipher_suites=tuple(int(item) for item in (getattr(listener, 'resolved_cipher_suites', ()) or (0x1302, 0x1301))),
        server_name=server_name,
    )


def _listener_server_name(listener: ListenerConfig) -> str:
    host = listener.host or 'localhost'
    if host in {'0.0.0.0', '::', ''}:
        return 'localhost'
    return host

__all__ = [name for name in globals() if not name.startswith('__')]
