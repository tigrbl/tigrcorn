from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any, Mapping

from .merge import merge_config_dicts

_FLAT_ENV_MAP = {
    "APP": ("app", "target"),
    "FACTORY": ("app", "factory"),
    "APP_DIR": ("app", "app_dir"),
    "LIFESPAN": ("app", "lifespan"),
    "ENV_FILE": ("app", "env_file"),
    "HOST": ("listeners", 0, "host"),
    "PORT": ("listeners", 0, "port"),
    "UDS": ("listeners", 0, "path"),
    "TRANSPORT": ("listeners", 0, "kind"),
    "USER": ("listeners", 0, "user"),
    "GROUP": ("listeners", 0, "group"),
    "UMASK": ("listeners", 0, "umask"),
    "LOG_LEVEL": ("logging", "level"),
    "ACCESS_LOG": ("logging", "access_log"),
    "USE_COLORS": ("logging", "use_colors"),
    "SSL_CERTFILE": ("tls", "certfile"),
    "SSL_KEYFILE": ("tls", "keyfile"),
    "SSL_KEYFILE_PASSWORD": ("tls", "keyfile_password"),
    "SSL_CA_CERTS": ("tls", "ca_certs"),
    "SSL_REQUIRE_CLIENT_CERT": ("tls", "require_client_cert"),
    "HTTP": ("http", "http_versions"),
    "PROTOCOL": ("listeners", 0, "protocols"),
    "MAX_BODY_SIZE": ("http", "max_body_size"),
    "MAX_HEADER_SIZE": ("http", "max_header_size"),
    "HTTP1_MAX_INCOMPLETE_EVENT_SIZE": ("http", "http1_max_incomplete_event_size"),
    "HTTP1_BUFFER_SIZE": ("http", "http1_buffer_size"),
    "HTTP1_HEADER_READ_TIMEOUT": ("http", "http1_header_read_timeout"),
    "HTTP1_KEEP_ALIVE": ("http", "http1_keep_alive"),
    "HTTP2_MAX_CONCURRENT_STREAMS": ("http", "http2_max_concurrent_streams"),
    "HTTP2_MAX_HEADERS_SIZE": ("http", "http2_max_headers_size"),
    "HTTP2_MAX_FRAME_SIZE": ("http", "http2_max_frame_size"),
    "HTTP2_ADAPTIVE_WINDOW": ("http", "http2_adaptive_window"),
    "HTTP2_INITIAL_CONNECTION_WINDOW_SIZE": ("http", "http2_initial_connection_window_size"),
    "HTTP2_INITIAL_STREAM_WINDOW_SIZE": ("http", "http2_initial_stream_window_size"),
    "HTTP2_KEEP_ALIVE_INTERVAL": ("http", "http2_keep_alive_interval"),
    "HTTP2_KEEP_ALIVE_TIMEOUT": ("http", "http2_keep_alive_timeout"),
    "WEBSOCKET_MAX_MESSAGE_SIZE": ("websocket", "max_message_size"),
    "WEBSOCKET_MAX_QUEUE": ("websocket", "max_queue"),
    "ROOT_PATH": ("proxy", "root_path"),
    "SERVER_HEADER": ("proxy", "server_header"),
    "DATE_HEADER": ("proxy", "include_date_header"),
    "HEADER": ("proxy", "default_headers"),
    "SERVER_NAME": ("proxy", "server_names"),
    "SSL_ALPN": ("tls", "alpn_protocols"),
    "SSL_OCSP_MODE": ("tls", "ocsp_mode"),
    "SSL_OCSP_CACHE_SIZE": ("tls", "ocsp_cache_size"),
    "SSL_OCSP_MAX_AGE": ("tls", "ocsp_max_age"),
    "SSL_CRL_MODE": ("tls", "crl_mode"),
    "SSL_CRL": ("tls", "crl"),
    "SSL_REVOCATION_FETCH": ("tls", "revocation_fetch"),
    "CONNECT_POLICY": ("http", "connect_policy"),
    "CONNECT_ALLOW": ("http", "connect_allow"),
    "TRAILER_POLICY": ("http", "trailer_policy"),
    "CONTENT_CODING_POLICY": ("http", "content_coding_policy"),
    "CONTENT_CODINGS": ("http", "content_codings"),
    "ALT_SVC": ("http", "alt_svc_headers"),
    "ALT_SVC_AUTO": ("http", "alt_svc_auto"),
    "ALT_SVC_MAX_AGE": ("http", "alt_svc_max_age"),
    "ALT_SVC_PERSIST": ("http", "alt_svc_persist"),
    "WEBSOCKET_COMPRESSION": ("websocket", "compression"),
    "STATIC_PATH_ROUTE": ("static", "route"),
    "STATIC_PATH_MOUNT": ("static", "mount"),
    "STATIC_PATH_DIR_TO_FILE": ("static", "dir_to_file"),
    "STATIC_PATH_INDEX_FILE": ("static", "index_file"),
    "STATIC_PATH_EXPIRES": ("static", "expires"),
    "RUNTIME": ("process", "runtime"),
    "WORKER_HEALTHCHECK_TIMEOUT": ("process", "worker_healthcheck_timeout"),
}


class EnvFileError(RuntimeError):
    pass


def _decode_scalar(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value and value[0] in "[{":
        try:
            return json.loads(value)
        except Exception:
            pass
    if "," in value:
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


def _nested_set(data: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    cursor: Any = data
    for index, segment in enumerate(path[:-1]):
        nxt = path[index + 1]
        if isinstance(segment, int):
            while len(cursor) <= segment:
                cursor.append({} if not isinstance(nxt, int) else [])
            cursor = cursor[segment]
            continue
        if segment not in cursor:
            cursor[segment] = [] if isinstance(nxt, int) else {}
        cursor = cursor[segment]
    last = path[-1]
    if isinstance(last, int):
        while len(cursor) <= last:
            cursor.append(None)
        cursor[last] = value
    else:
        cursor[last] = value


def load_env_file(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        raise EnvFileError(f'env file does not exist: {env_path}')
    result: dict[str, str] = {}
    for line_no, raw_line in enumerate(env_path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            raise EnvFileError(f'invalid env file line {line_no}: {raw_line!r}')
        key, raw_value = line.split('=', 1)
        key = key.strip()
        if not key:
            raise EnvFileError(f'invalid env file line {line_no}: empty key')
        value = raw_value.strip()
        if value and value[0] in {'"', "'"}:
            try:
                parsed = shlex.split(f'VALUE={value}', posix=True)
                value = parsed[0].split('=', 1)[1]
            except Exception as exc:
                raise EnvFileError(f'invalid quoted value on line {line_no}') from exc
        elif ' #' in value:
            value = value.split(' #', 1)[0].rstrip()
        result[key] = value
    return result


def load_env_config(prefix: str = "TIGRCORN", *, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    normalized_prefix = prefix.upper().replace("-", "_")
    nested_prefix = f"{normalized_prefix}__"
    flat_prefix = f"{normalized_prefix}_"
    nested: dict[str, Any] = {}
    flat: dict[str, Any] = {}

    for key, raw_value in env.items():
        if key.startswith(nested_prefix):
            path_bits = key[len(nested_prefix):].split("__")
            path: list[str | int] = []
            for bit in path_bits:
                if bit.isdigit():
                    path.append(int(bit))
                else:
                    path.append(bit.lower())
            _nested_set(nested, tuple(path), _decode_scalar(raw_value))
        elif key.startswith(flat_prefix):
            name = key[len(flat_prefix):]
            path = _FLAT_ENV_MAP.get(name)
            if path is not None:
                _nested_set(flat, path, _decode_scalar(raw_value))
    return merge_config_dicts(flat, nested)
