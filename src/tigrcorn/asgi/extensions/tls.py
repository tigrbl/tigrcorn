from __future__ import annotations


def tls_extension(selected_alpn_protocol: str | None = None, peer_cert: dict | None = None) -> dict:
    ext = {}
    if selected_alpn_protocol is not None:
        ext['selected_alpn_protocol'] = selected_alpn_protocol
    if peer_cert is not None:
        ext['peer_cert'] = peer_cert
    return ext
