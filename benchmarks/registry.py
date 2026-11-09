from __future__ import annotations

from importlib import import_module


_DRIVER_REGISTRY: dict[str, tuple[str, str]] = {
    'http11_baseline': ('drivers_http', 'http11_baseline_driver'),
    'http11_keepalive': ('drivers_http', 'http11_keepalive_driver'),
    'http11_chunked_upload_download': ('drivers_http', 'http11_chunked_driver'),
    'http2_multiplex': ('drivers_http', 'http2_multiplex_driver'),
    'http2_tls': ('drivers_http', 'http2_tls_driver'),
    'http3_clean_network': ('drivers_http', 'http3_clean_driver'),
    'http3_loss_jitter': ('drivers_http', 'http3_loss_driver'),
    'ws_http11': ('drivers_websocket', 'ws_http11_driver'),
    'ws_http11_permessage_deflate': ('drivers_websocket', 'ws_http11_deflate_driver'),
    'ws_http2': ('drivers_websocket', 'ws_http2_driver'),
    'ws_http2_permessage_deflate': ('drivers_websocket', 'ws_http2_deflate_driver'),
    'ws_http3': ('drivers_websocket', 'ws_http3_driver'),
    'ws_http3_permessage_deflate': ('drivers_websocket', 'ws_http3_deflate_driver'),
    'ws_fanout_broadcast': ('drivers_websocket', 'ws_fanout_driver'),
    'tls_handshake': ('drivers_tls', 'tls_handshake_driver'),
    'mtls_handshake': ('drivers_tls', 'mtls_handshake_driver'),
    'ocsp_strict_mode': ('drivers_tls', 'ocsp_strict_driver'),
    'alpn_negotiation_cost': ('drivers_tls', 'alpn_negotiation_driver'),
    'connect_relay_throughput': ('drivers_semantic', 'connect_relay_driver'),
    'trailers_under_load': ('drivers_semantic', 'trailers_driver'),
    'content_coding_under_load': ('drivers_semantic', 'content_coding_driver'),
    'logging_off': ('drivers_operator', 'logging_off_driver'),
    'logging_on': ('drivers_operator', 'logging_on_driver'),
    'metrics_off': ('drivers_operator', 'metrics_off_driver'),
    'metrics_on': ('drivers_operator', 'metrics_on_driver'),
    'proxy_headers_off': ('drivers_operator', 'proxy_headers_off_driver'),
    'proxy_headers_on': ('drivers_operator', 'proxy_headers_on_driver'),
    'worker_scaleout': ('drivers_operator', 'worker_scaleout_driver'),
    'graceful_drain': ('drivers_operator', 'graceful_drain_driver'),
    'reload_overhead': ('drivers_operator', 'reload_overhead_driver'),
    'runtime_scheduler': ('drivers_runtime', 'runtime_scheduler_driver'),
    'http3_peer_prepare': ('drivers_peer', 'http3_peer_prepare_driver'),
    'websocket_peer_frame': ('drivers_ws_peer', 'websocket_peer_frame_driver'),
    'wrk2_http11_constant_rate': ('drivers_wrk2', 'wrk2_http11_constant_rate_driver'),
    'wrk2_http11_step_rate': ('drivers_wrk2', 'wrk2_http11_step_rate_driver'),
    'vegeta_http11_constant_rate': ('drivers_vegeta', 'vegeta_http11_constant_rate_driver'),
    'vegeta_http11_step_rate': ('drivers_vegeta', 'vegeta_http11_step_rate_driver'),
    'vegeta_http11_recovery_pattern': ('drivers_vegeta', 'vegeta_http11_recovery_pattern_driver'),
}


def get_driver(name: str):
    try:
        module, attribute = _DRIVER_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f'unknown benchmark driver: {name}') from exc
    return getattr(import_module(f'.{module}', __package__), attribute)


__all__ = ['get_driver']
