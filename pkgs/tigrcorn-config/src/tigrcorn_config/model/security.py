from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tigrcorn_core.constants import DEFAULT_SERVER_HEADER


@dataclass(slots=True)
class TLSConfig:
    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | bytes | None = None
    ca_certs: str | None = None
    require_client_cert: bool = False
    ciphers: str | None = None
    resolved_cipher_suites: tuple[int, ...] = ()
    alpn_protocols: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])
    ocsp_mode: Literal["off", "soft-fail", "require"] = "off"
    ocsp_soft_fail: bool = False
    ocsp_cache_size: int = 128
    ocsp_max_age: float | None = 43_200.0
    crl_mode: Literal["off", "soft-fail", "require"] = "off"
    crl: str | None = None
    revocation_fetch: bool = True


@dataclass(slots=True)
class ProxyConfig:
    proxy_headers: bool = False
    forwarded_allow_ips: list[str] = field(default_factory=list)
    root_path: str = ""
    server_header: bytes | str = DEFAULT_SERVER_HEADER
    include_server_header: bool = False
    include_date_header: bool = True
    default_headers: list[tuple[bytes | str, bytes | str] | list[bytes | str] | dict[str, bytes | str]] = field(default_factory=list)
    server_names: list[str] = field(default_factory=list)
