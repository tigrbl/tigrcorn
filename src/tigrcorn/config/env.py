from __future__ import annotations

import json
import os
from typing import Any, Mapping

from .merge import merge_config_dicts

_FLAT_ENV_MAP = {
    "APP": ("app", "target"),
    "FACTORY": ("app", "factory"),
    "APP_DIR": ("app", "app_dir"),
    "LIFESPAN": ("app", "lifespan"),
    "HOST": ("listeners", 0, "host"),
    "PORT": ("listeners", 0, "port"),
    "UDS": ("listeners", 0, "path"),
    "TRANSPORT": ("listeners", 0, "kind"),
    "LOG_LEVEL": ("logging", "level"),
    "ACCESS_LOG": ("logging", "access_log"),
    "SSL_CERTFILE": ("tls", "certfile"),
    "SSL_KEYFILE": ("tls", "keyfile"),
    "SSL_CA_CERTS": ("tls", "ca_certs"),
    "SSL_REQUIRE_CLIENT_CERT": ("tls", "require_client_cert"),
    "HTTP": ("http", "http_versions"),
    "PROTOCOL": ("listeners", 0, "protocols"),
    "MAX_BODY_SIZE": ("http", "max_body_size"),
    "MAX_HEADER_SIZE": ("http", "max_header_size"),
    "WEBSOCKET_MAX_MESSAGE_SIZE": ("websocket", "max_message_size"),
    "ROOT_PATH": ("proxy", "root_path"),
    "SSL_ALPN": ("tls", "alpn_protocols"),
    "SSL_OCSP_MODE": ("tls", "ocsp_mode"),
    "SSL_OCSP_CACHE_SIZE": ("tls", "ocsp_cache_size"),
    "SSL_OCSP_MAX_AGE": ("tls", "ocsp_max_age"),
    "SSL_CRL_MODE": ("tls", "crl_mode"),
    "SSL_REVOCATION_FETCH": ("tls", "revocation_fetch"),
    "CONNECT_POLICY": ("http", "connect_policy"),
    "CONNECT_ALLOW": ("http", "connect_allow"),
    "TRAILER_POLICY": ("http", "trailer_policy"),
    "CONTENT_CODING_POLICY": ("http", "content_coding_policy"),
    "CONTENT_CODINGS": ("http", "content_codings"),
    "WEBSOCKET_COMPRESSION": ("websocket", "compression"),
}


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
