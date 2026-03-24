from __future__ import annotations

from typing import Callable

from .drivers_http import (
    http11_baseline_driver,
    http11_chunked_driver,
    http11_keepalive_driver,
    http2_multiplex_driver,
    http2_tls_driver,
    http3_clean_driver,
    http3_loss_driver,
)
from .drivers_operator import (
    graceful_drain_driver,
    logging_off_driver,
    logging_on_driver,
    metrics_off_driver,
    metrics_on_driver,
    proxy_headers_off_driver,
    proxy_headers_on_driver,
    reload_overhead_driver,
    worker_scaleout_driver,
)
from .drivers_semantic import connect_relay_driver, content_coding_driver, trailers_driver
from .drivers_tls import alpn_negotiation_driver, mtls_handshake_driver, ocsp_strict_driver, tls_handshake_driver
from .drivers_websocket import (
    ws_fanout_driver,
    ws_http11_deflate_driver,
    ws_http11_driver,
    ws_http2_deflate_driver,
    ws_http2_driver,
    ws_http3_deflate_driver,
    ws_http3_driver,
)

_DRIVER_REGISTRY: dict[str, Callable[..., dict]] = {
    'http11_baseline': http11_baseline_driver,
    'http11_keepalive': http11_keepalive_driver,
    'http11_chunked_upload_download': http11_chunked_driver,
    'http2_multiplex': http2_multiplex_driver,
    'http2_tls': http2_tls_driver,
    'http3_clean_network': http3_clean_driver,
    'http3_loss_jitter': http3_loss_driver,
    'ws_http11': ws_http11_driver,
    'ws_http11_permessage_deflate': ws_http11_deflate_driver,
    'ws_http2': ws_http2_driver,
    'ws_http2_permessage_deflate': ws_http2_deflate_driver,
    'ws_http3': ws_http3_driver,
    'ws_http3_permessage_deflate': ws_http3_deflate_driver,
    'ws_fanout_broadcast': ws_fanout_driver,
    'tls_handshake': tls_handshake_driver,
    'mtls_handshake': mtls_handshake_driver,
    'ocsp_strict_mode': ocsp_strict_driver,
    'alpn_negotiation_cost': alpn_negotiation_driver,
    'connect_relay_throughput': connect_relay_driver,
    'trailers_under_load': trailers_driver,
    'content_coding_under_load': content_coding_driver,
    'logging_off': logging_off_driver,
    'logging_on': logging_on_driver,
    'metrics_off': metrics_off_driver,
    'metrics_on': metrics_on_driver,
    'proxy_headers_off': proxy_headers_off_driver,
    'proxy_headers_on': proxy_headers_on_driver,
    'worker_scaleout': worker_scaleout_driver,
    'graceful_drain': graceful_drain_driver,
    'reload_overhead': reload_overhead_driver,
}


def get_driver(name: str):
    try:
        return _DRIVER_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f'unknown benchmark driver: {name}') from exc


__all__ = ['get_driver']
