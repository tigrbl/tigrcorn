from __future__ import annotations

from tigrcorn.config.model import ListenerConfig, ServerConfig
from tigrcorn.errors import ConfigError
from tigrcorn.security.alpn import normalize_alpn_list
from tigrcorn.security.tls_cipher_policy import parse_tls13_cipher_allowlist


def _ensure_list(value: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return [str(item) for item in value]


def normalize_config(config: ServerConfig) -> None:
    config.logging.level = config.logging.level.lower()
    config.app.env_prefix = config.app.env_prefix.upper().replace('-', '_')
    config.http.http_versions = [str(v).replace('http/', '') for v in _ensure_list(config.http.http_versions)] or ["1.1", "2"]
    config.http.content_codings = [str(v).lower() for v in _ensure_list(config.http.content_codings)]
    config.app.reload_dirs = [str(v) for v in _ensure_list(config.app.reload_dirs)]
    config.app.reload_include = [str(v) for v in _ensure_list(config.app.reload_include)]
    config.app.reload_exclude = [str(v) for v in _ensure_list(config.app.reload_exclude)]
    config.tls.alpn_protocols = normalize_alpn_list([str(v).strip().lower() for v in _ensure_list(config.tls.alpn_protocols)])

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
    config.http.connect_allow = [str(v).strip() for v in _ensure_list(config.http.connect_allow) if str(v).strip()]
    config.proxy.root_path = '' if not config.proxy.root_path else ('/' + config.proxy.root_path.lstrip('/')).rstrip('/') or '/'
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
            if listener.revocation_fetch is True and config.tls.revocation_fetch is not True:
                listener.revocation_fetch = config.tls.revocation_fetch
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_certfile and config.tls.certfile and not listener.insecure_bind:
            listener.ssl_certfile = config.tls.certfile
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_keyfile and config.tls.keyfile and not listener.insecure_bind:
            listener.ssl_keyfile = config.tls.keyfile
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_ca_certs and config.tls.ca_certs and not listener.insecure_bind:
            listener.ssl_ca_certs = config.tls.ca_certs
        if listener.kind in {"tcp", "unix", "udp"} and config.tls.require_client_cert and not listener.insecure_bind:
            listener.ssl_require_client_cert = True
        if listener.kind in {"tcp", "unix", "udp"} and not listener.ssl_ciphers and config.tls.ciphers and not listener.insecure_bind:
            listener.ssl_ciphers = config.tls.ciphers
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
            if "http3" in listener.protocols and "quic" not in listener.protocols:
                listener.protocols.insert(0, "quic")
            listener.max_datagram_size = int(config.quic.max_datagram_size or listener.max_datagram_size)
            listener.quic_require_retry = bool(config.quic.require_retry or listener.quic_require_retry)
            listener.quic_secret = config.quic.quic_secret or listener.quic_secret
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
