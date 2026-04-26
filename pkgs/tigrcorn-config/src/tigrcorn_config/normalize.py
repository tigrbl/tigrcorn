from __future__ import annotations

import secrets

from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_core.constants import (
    DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE,
    DEFAULT_HTTP2_INITIAL_STREAM_WINDOW_SIZE,
    SUPPORTED_WORKER_CLASS_ALIASES,
)
from tigrcorn_core.errors import ConfigError
from tigrcorn_security.alpn import normalize_alpn_list
from tigrcorn_security.tls_cipher_policy import parse_tls13_cipher_allowlist
from tigrcorn_core.utils.headers import normalize_header_entries




def _normalize_umask(value: int | str | None) -> int | None:
    if value is None or value == '':
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    if raw.startswith('0o'):
        return int(raw, 8)
    if raw.startswith('0x'):
        return int(raw, 16)
    if raw.startswith('0') and raw != '0':
        return int(raw, 8)
    try:
        return int(raw, 8)
    except ValueError:
        return int(raw, 10)

def _ensure_list(value: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return [str(item) for item in value]


def normalize_config(config: ServerConfig) -> None:
    config.logging.level = config.logging.level.lower()
    config.app.interface = str(config.app.interface or 'auto').lower().replace('_', '-')  # type: ignore[assignment]
    config.app.env_prefix = config.app.env_prefix.upper().replace('-', '_')
    config.process.runtime = str(config.process.runtime or 'auto').lower()
    config.http.http_versions = [str(v).replace('http/', '') for v in _ensure_list(config.http.http_versions)] or ["1.1", "2"]
    config.http.content_codings = [str(v).lower() for v in _ensure_list(config.http.content_codings)]
    config.http.http1_max_incomplete_event_size = int(config.http.max_header_size if config.http.http1_max_incomplete_event_size is None else config.http.http1_max_incomplete_event_size)
    config.http.http1_buffer_size = int(config.http.http1_buffer_size or 65_536)
    if config.http.http1_header_read_timeout is not None:
        config.http.http1_header_read_timeout = float(config.http.http1_header_read_timeout)
    config.http.http1_keep_alive = True if config.http.http1_keep_alive is None else bool(config.http.http1_keep_alive)
    config.http.http2_max_concurrent_streams = int(
        config.scheduler.max_streams if config.http.http2_max_concurrent_streams is None and config.scheduler.max_streams is not None else (128 if config.http.http2_max_concurrent_streams is None else config.http.http2_max_concurrent_streams)
    )
    config.http.http2_max_headers_size = int(config.http.max_header_size if config.http.http2_max_headers_size is None else config.http.http2_max_headers_size)
    config.http.http2_max_frame_size = int(16_384 if config.http.http2_max_frame_size is None else config.http.http2_max_frame_size)
    config.http.http2_adaptive_window = bool(config.http.http2_adaptive_window)
    config.http.http2_initial_connection_window_size = max(
        DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE,
        int(DEFAULT_HTTP2_INITIAL_CONNECTION_WINDOW_SIZE if config.http.http2_initial_connection_window_size is None else config.http.http2_initial_connection_window_size),
    )
    config.http.http2_initial_stream_window_size = int(
        DEFAULT_HTTP2_INITIAL_STREAM_WINDOW_SIZE if config.http.http2_initial_stream_window_size is None else config.http.http2_initial_stream_window_size
    )
    if config.http.http2_keep_alive_interval is not None:
        config.http.http2_keep_alive_interval = float(config.http.http2_keep_alive_interval)
    if config.http.http2_keep_alive_timeout is not None:
        config.http.http2_keep_alive_timeout = float(config.http.http2_keep_alive_timeout)
    config.websocket.max_queue = int(config.websocket.max_queue or 32)
    if config.webtransport.max_sessions is not None:
        config.webtransport.max_sessions = int(config.webtransport.max_sessions)
    if config.webtransport.max_streams is not None:
        config.webtransport.max_streams = int(config.webtransport.max_streams)
    if config.webtransport.max_datagram_size is not None:
        config.webtransport.max_datagram_size = int(config.webtransport.max_datagram_size)
    config.webtransport.origins = [str(v).strip() for v in _ensure_list(config.webtransport.origins) if str(v).strip()]
    if config.webtransport.path is not None:
        path = str(config.webtransport.path).strip()
        config.webtransport.path = ('/' + path.lstrip('/')).rstrip('/') or '/'
    config.http.alt_svc_headers = [bytes(v).decode('latin1') if isinstance(v, (bytes, bytearray, memoryview)) else str(v).strip() for v in _ensure_list(config.http.alt_svc_headers) if str(v).strip()]
    config.app.reload_dirs = [str(v) for v in _ensure_list(config.app.reload_dirs)]
    config.app.reload_include = [str(v) for v in _ensure_list(config.app.reload_include)]
    config.app.reload_exclude = [str(v) for v in _ensure_list(config.app.reload_exclude)]
    config.tls.alpn_protocols = normalize_alpn_list([str(v).strip().lower() for v in _ensure_list(config.tls.alpn_protocols)])
    if isinstance(config.tls.keyfile_password, bytes):
        config.tls.keyfile_password = bytes(config.tls.keyfile_password)
    elif config.tls.keyfile_password is not None:
        config.tls.keyfile_password = str(config.tls.keyfile_password)
    if config.tls.crl is not None:
        normalized_crl = str(config.tls.crl).strip()
        config.tls.crl = normalized_crl or None

    if config.tls.ciphers is not None:
        try:
            config.tls.resolved_cipher_suites = parse_tls13_cipher_allowlist(config.tls.ciphers)
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f'invalid ssl_ciphers expression: {config.tls.ciphers!r}') from exc
    else:
        config.tls.resolved_cipher_suites = ()
    config.proxy.forwarded_allow_ips = [str(v) for v in _ensure_list(config.proxy.forwarded_allow_ips)]
    config.proxy.server_names = [str(v).strip().lower() for v in _ensure_list(config.proxy.server_names) if str(v).strip()]
    config.proxy.default_headers = normalize_header_entries(config.proxy.default_headers)
    config.http.connect_allow = [str(v).strip() for v in _ensure_list(config.http.connect_allow) if str(v).strip()]
    config.proxy.root_path = '' if not config.proxy.root_path else ('/' + config.proxy.root_path.lstrip('/')).rstrip('/') or '/'
    if config.static.mount is not None:
        config.static.mount = str(config.static.mount)
        if not config.static.route:
            config.static.route = '/'
    if config.static.route:
        config.static.route = ('/' + str(config.static.route).lstrip('/')).rstrip('/') or '/'
    if config.static.index_file is not None:
        normalized_index = str(config.static.index_file).strip()
        config.static.index_file = normalized_index or None
    legacy_runtime_aliases = set(SUPPORTED_WORKER_CLASS_ALIASES)
    if config.process.worker_class in legacy_runtime_aliases:
        if config.process.runtime == 'auto':
            config.process.runtime = config.process.worker_class
        config.process.worker_class = 'local'
    if config.process.workers > 1 and config.process.worker_class == 'local':
        config.process.worker_class = 'process'
    if config.metrics.bind or config.metrics.statsd_host or config.metrics.otel_endpoint:
        config.metrics.enabled = True
    if isinstance(config.proxy.server_header, str):
        config.proxy.server_header = config.proxy.server_header.encode('latin1') if config.proxy.server_header else b''
    if not config.proxy.include_server_header:
        config.proxy.server_header = b''

    if not config.listeners:
        config.listeners = [ListenerConfig()]

    for listener in config.listeners:
        listener.kind = listener.kind.lower()  # type: ignore[assignment]
        listener.http_versions = [str(v).replace('http/', '') for v in _ensure_list(listener.http_versions)] or list(config.http.http_versions)
        listener.protocols = [str(v).lower() for v in _ensure_list(listener.protocols)]
        if listener.kind in {"tcp", "unix", "udp"}:
            base_alpn = listener.alpn_protocols or config.tls.alpn_protocols
            if listener.kind == 'udp' and not listener.alpn_protocols and (not config.tls.alpn_protocols or config.tls.alpn_protocols == ['h2', 'http/1.1']):
                base_alpn = ['h3']
            listener.alpn_protocols = normalize_alpn_list(base_alpn, for_udp=listener.kind == 'udp')
            if listener.ocsp_mode == 'off' and config.tls.ocsp_mode != 'off':
                listener.ocsp_mode = config.tls.ocsp_mode
            if not listener.ocsp_soft_fail and config.tls.ocsp_soft_fail:
                listener.ocsp_soft_fail = config.tls.ocsp_soft_fail
            if listener.ocsp_cache_size == 128 and config.tls.ocsp_cache_size != 128:
                listener.ocsp_cache_size = config.tls.ocsp_cache_size
            if listener.ocsp_max_age == 43_200.0 and config.tls.ocsp_max_age != 43_200.0:
                listener.ocsp_max_age = config.tls.ocsp_max_age
            if listener.crl_mode == 'off' and config.tls.crl_mode != 'off':
                listener.crl_mode = config.tls.crl_mode
            if not getattr(listener, 'ssl_crl', None) and config.tls.crl:
                listener.ssl_crl = config.tls.crl
            if listener.revocation_fetch is True and config.tls.revocation_fetch is not True:
                listener.revocation_fetch = config.tls.revocation_fetch
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_certfile and config.tls.certfile and not listener.insecure_bind:
            listener.ssl_certfile = config.tls.certfile
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_keyfile and config.tls.keyfile and not listener.insecure_bind:
            listener.ssl_keyfile = config.tls.keyfile
        if listener.kind in {"tcp", "unix", "udp"} and getattr(listener, 'ssl_keyfile_password', None) is None and config.tls.keyfile_password is not None and not listener.insecure_bind:
            listener.ssl_keyfile_password = config.tls.keyfile_password
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_ca_certs and config.tls.ca_certs and not listener.insecure_bind:
            listener.ssl_ca_certs = config.tls.ca_certs
        if listener.kind in {"tcp", "unix", "udp"} and config.tls.require_client_cert and not listener.insecure_bind:
            listener.ssl_require_client_cert = True
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_ciphers and config.tls.ciphers and not listener.insecure_bind:
            listener.ssl_ciphers = config.tls.ciphers
        if getattr(listener, 'ssl_keyfile_password', None) is not None and not isinstance(listener.ssl_keyfile_password, bytes):
            listener.ssl_keyfile_password = str(listener.ssl_keyfile_password)
        if getattr(listener, 'ssl_crl', None) is not None:
            normalized_listener_crl = str(listener.ssl_crl).strip()
            listener.ssl_crl = normalized_listener_crl or None
        if listener.user is not None and isinstance(listener.user, str) and listener.user.strip().isdigit():
            listener.user = int(listener.user.strip())
        if listener.group is not None and isinstance(listener.group, str) and listener.group.strip().isdigit():
            listener.group = int(listener.group.strip())
        listener.umask = _normalize_umask(listener.umask)
        if listener.ssl_ciphers is not None:
            try:
                listener.resolved_cipher_suites = parse_tls13_cipher_allowlist(listener.ssl_ciphers)
            except ConfigError:
                raise
            except Exception as exc:
                raise ConfigError(f'invalid listener ssl_ciphers expression: {listener.ssl_ciphers!r}') from exc
        else:
            listener.resolved_cipher_suites = config.tls.resolved_cipher_suites
        if not listener.protocols:
            if listener.kind == "udp":
                listener.protocols = ["quic"]
                if "3" in listener.http_versions:
                    listener.protocols.append("http3")
            elif listener.kind == "pipe":
                listener.protocols = ["rawframed"] if listener.pipe_mode == "rawframed" else ["custom"]
            elif listener.kind == "inproc":
                listener.protocols = ["custom"]
            else:
                listener.protocols = ["http1"]
                if "2" in listener.http_versions:
                    listener.protocols.append("http2")
                if config.websocket.enabled and listener.websocket:
                    listener.protocols.append("websocket")
        listener.websocket = config.websocket.enabled if listener.websocket else listener.websocket
        if listener.kind == "udp":
            if "webtransport" in listener.protocols:
                if "quic" not in listener.protocols:
                    listener.protocols.insert(0, "quic")
                if "http3" not in listener.protocols:
                    insert_at = listener.protocols.index("quic") + 1 if "quic" in listener.protocols else 0
                    listener.protocols.insert(insert_at, "http3")
                if "3" not in listener.http_versions:
                    listener.http_versions.append("3")
            if "http3" in listener.protocols and "quic" not in listener.protocols:
                listener.protocols.insert(0, "quic")
            listener.max_datagram_size = int(config.quic.max_datagram_size or listener.max_datagram_size)
            listener.quic_require_retry = bool(config.quic.require_retry or listener.quic_require_retry)
            listener.quic_secret = listener.quic_secret or config.quic.quic_secret or secrets.token_bytes(32)
        if not listener.scheme:
            if listener.kind == "udp":
                listener.scheme = "https" if "http3" in listener.enabled_protocols else "quic"
            elif listener.kind == "pipe":
                listener.scheme = "tigrcorn+pipe"
            elif listener.kind == "unix":
                listener.scheme = "https" if listener.ssl_enabled else "http"
            elif listener.kind == "inproc":
                listener.scheme = "tigrcorn+inproc"
            else:
                listener.scheme = "https" if listener.ssl_enabled else "http"
