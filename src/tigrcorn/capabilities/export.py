from __future__ import annotations

from importlib import util as importlib_util
from typing import Any, Iterable, Mapping

from tigrcorn_config.profiles import list_blessed_profiles, resolve_effective_profile_mapping
from tigrcorn_core.constants import SUPPORTED_RUNTIMES
from tigrcorn_transports.registry import TRANSPORTS

from .model import (
    CapabilityDefinition,
    CapabilityExport,
    CapabilityRecord,
    CapabilityState,
    UnsupportedCapabilityError,
)


SCHEMA_VERSION = "1.0"
REGISTRY_NAME = "tigrcorn.runtime-capabilities"


_CATALOG: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition("certification.deployment_profiles", "certification", "Deployment profile registry", True, certifiable=True, certified=True),
    CapabilityDefinition("certification.release_validation", "certification", "Release validation tooling", True, certifiable=True, certified=False),
    CapabilityDefinition("certification.ssot_boundary", "certification", "SSOT boundary evidence", True, certifiable=True, certified=False),
    CapabilityDefinition("delivery.static", "delivery", "Static delivery", True, certifiable=True, certified=False),
    CapabilityDefinition("observability.metrics", "observability", "Metrics export", True, certifiable=True, certified=False),
    CapabilityDefinition("observability.otel", "observability", "OpenTelemetry export", True, certifiable=True, certified=False),
    CapabilityDefinition("observability.statsd", "observability", "StatsD export", True, certifiable=True, certified=False),
    CapabilityDefinition("observability.structured_logging", "observability", "Structured logging", True, certifiable=True, certified=False),
    CapabilityDefinition("protocol.http1", "protocol", "HTTP/1.1", True, certifiable=True, certified=True),
    CapabilityDefinition("protocol.http2", "protocol", "HTTP/2", importlib_util.find_spec("h2") is not None, certifiable=True, certified=True, optional=True),
    CapabilityDefinition("protocol.http3", "protocol", "HTTP/3", importlib_util.find_spec("aioquic") is not None, certifiable=True, certified=True, optional=True),
    CapabilityDefinition("protocol.lifespan", "protocol", "ASGI lifespan", True, certifiable=True, certified=True),
    CapabilityDefinition("protocol.quic", "protocol", "QUIC protocol", importlib_util.find_spec("aioquic") is not None, certifiable=True, certified=True, optional=True),
    CapabilityDefinition("protocol.websocket", "protocol", "WebSocket", importlib_util.find_spec("websockets") is not None or importlib_util.find_spec("wsproto") is not None, certifiable=True, certified=True, optional=True),
    CapabilityDefinition("protocol.webtransport", "protocol", "WebTransport", True, certifiable=True, certified=False),
    CapabilityDefinition("runtime.embedded", "runtime", "Embedded runtime API", True, certifiable=True, certified=False),
    CapabilityDefinition("runtime.lifecycle", "runtime", "Lifecycle management", True, certifiable=True, certified=True),
    CapabilityDefinition("runtime.worker_pool", "runtime", "Worker process management", True, certifiable=True, certified=False),
    CapabilityDefinition("tls.alpn", "tls", "ALPN negotiation", True, certifiable=True, certified=True),
    CapabilityDefinition("tls.crl", "tls", "CRL revocation handling", True, certifiable=True, certified=True),
    CapabilityDefinition("tls.mtls", "tls", "Mutual TLS", True, certifiable=True, certified=False),
    CapabilityDefinition("tls.ocsp", "tls", "OCSP revocation handling", True, certifiable=True, certified=True),
    CapabilityDefinition("tls.tls13", "tls", "TLS 1.3", True, certifiable=True, certified=True),
    CapabilityDefinition("tls.x509", "tls", "X.509 path validation", True, certifiable=True, certified=True),
    CapabilityDefinition("transport.inproc", "transport", "In-process transport", "inproc" in TRANSPORTS, certifiable=True, certified=False),
    CapabilityDefinition("transport.pipe", "transport", "Pipe transport", "pipe" in TRANSPORTS, certifiable=True, certified=False),
    CapabilityDefinition("transport.quic", "transport", "QUIC transport", "quic" in TRANSPORTS and importlib_util.find_spec("aioquic") is not None, certifiable=True, certified=True, optional=True),
    CapabilityDefinition("transport.tcp", "transport", "TCP transport", "tcp" in TRANSPORTS, certifiable=True, certified=True),
    CapabilityDefinition("transport.udp", "transport", "UDP transport", "udp" in TRANSPORTS, certifiable=True, certified=False),
    CapabilityDefinition("transport.unix", "transport", "Unix domain socket transport", "unix" in TRANSPORTS, certifiable=True, certified=False),
)


_KNOWN_IDS = frozenset(item.id for item in _CATALOG)


def _normalize_profile(profile: str | None) -> str:
    return (profile or "default").strip().lower() or "default"


def _iter_mapping_values(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _iter_mapping_values(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _iter_mapping_values(item)


def _configured_capability_ids(config: Mapping[str, Any]) -> set[str]:
    configured = {
        "certification.deployment_profiles",
        "certification.release_validation",
        "certification.ssot_boundary",
        "protocol.lifespan",
        "runtime.embedded",
        "runtime.lifecycle",
    }

    app = config.get("app")
    if isinstance(app, Mapping):
        runtime = app.get("runtime")
        if runtime in SUPPORTED_RUNTIMES:
            configured.add("runtime.lifecycle")

    http = config.get("http")
    if isinstance(http, Mapping):
        for version in http.get("http_versions") or ():
            if version == "1.1":
                configured.add("protocol.http1")
            elif str(version) == "2":
                configured.add("protocol.http2")
            elif str(version) == "3":
                configured.add("protocol.http3")
                configured.add("protocol.quic")
                configured.add("transport.quic")
        if http.get("alt_svc_auto") or http.get("alt_svc_headers"):
            configured.add("protocol.http3")
        if http.get("content_codings"):
            configured.add("delivery.static")

    websocket = config.get("websocket")
    if isinstance(websocket, Mapping) and websocket.get("enabled"):
        configured.add("protocol.websocket")

    static = config.get("static")
    if isinstance(static, Mapping) and (static.get("route") or static.get("mount")):
        configured.add("delivery.static")

    tls = config.get("tls")
    if isinstance(tls, Mapping):
        if tls.get("certfile") or tls.get("keyfile") or tls.get("alpn_protocols"):
            configured.update({"tls.tls13", "tls.alpn", "tls.x509"})
        if tls.get("ocsp_mode") and tls.get("ocsp_mode") != "off":
            configured.add("tls.ocsp")
        if tls.get("crl_mode") and tls.get("crl_mode") != "off":
            configured.add("tls.crl")
        if tls.get("require_client_cert"):
            configured.add("tls.mtls")

    observability = config.get("observability")
    if isinstance(observability, Mapping):
        if observability.get("metrics"):
            configured.add("observability.metrics")
        if observability.get("structured_log"):
            configured.add("observability.structured_logging")
        if observability.get("otel_endpoint"):
            configured.add("observability.otel")
        if observability.get("statsd_host"):
            configured.add("observability.statsd")

    for value in _iter_mapping_values(config.get("listeners")):
        if not isinstance(value, Mapping):
            continue
        kind = value.get("kind")
        if isinstance(kind, str):
            configured.add(f"transport.{kind}")
        for protocol in value.get("protocols") or ():
            if protocol == "quic":
                configured.update({"protocol.quic", "transport.quic"})
            elif protocol in {"http1", "http2", "http3", "websocket", "webtransport"}:
                configured.add(f"protocol.{protocol}")
        for version in value.get("http_versions") or ():
            if version == "1.1":
                configured.add("protocol.http1")
            elif str(version) == "2":
                configured.add("protocol.http2")
            elif str(version) == "3":
                configured.update({"protocol.http3", "protocol.quic", "transport.quic"})
        if value.get("websocket"):
            configured.add("protocol.websocket")
        if value.get("alpn_protocols"):
            configured.add("tls.alpn")

    return configured


def _record(definition: CapabilityDefinition, configured_ids: set[str]) -> CapabilityRecord:
    configured = definition.id in configured_ids
    enabled = definition.compiled and configured
    certified = enabled and definition.certified
    if not definition.compiled:
        state = CapabilityState.UNAVAILABLE if definition.optional else CapabilityState.UNSUPPORTED
        reason = "optional dependency is not available" if definition.optional else "capability is not compiled into this distribution"
    elif certified:
        state = CapabilityState.CERTIFIED
        reason = "configured and certified for the selected profile"
    elif enabled:
        state = CapabilityState.ENABLED
        reason = "configured but not certified for the selected profile"
    elif configured:
        state = CapabilityState.CONFIGURED
        reason = "configured but unavailable"
    else:
        state = CapabilityState.COMPILED
        reason = "compiled into the distribution but not selected by the profile"
    return CapabilityRecord(
        id=definition.id,
        domain=definition.domain,
        name=definition.name,
        state=state,
        compiled=definition.compiled,
        configured=configured,
        enabled=enabled,
        certified=certified,
        certifiable=definition.certifiable,
        reason=reason,
    )


def capability_ids() -> tuple[str, ...]:
    return tuple(sorted(_KNOWN_IDS))


def require_supported(required_capabilities: Iterable[str], *, profile: str = "default") -> None:
    payload = export(profile=profile)
    records = {item["id"]: item for item in payload["capabilities"]}
    errors: list[str] = []
    for capability_id in required_capabilities:
        record = records.get(capability_id)
        if record is None:
            errors.append(f"unsupported capability requirement: {capability_id}")
        elif not record["enabled"]:
            errors.append(f"capability is not enabled for profile {profile!r}: {capability_id}")
    if errors:
        raise UnsupportedCapabilityError("; ".join(errors))


def export(*, profile: str = "default") -> dict[str, Any]:
    profile_name = _normalize_profile(profile)
    if profile_name not in list_blessed_profiles():
        raise ValueError(f"unknown blessed profile: {profile_name!r}")

    config = resolve_effective_profile_mapping(profile_name)
    configured_ids = _configured_capability_ids(config)
    profile_errors = tuple(
        f"configured capability is not supported: {capability_id}"
        for capability_id in sorted(configured_ids - _KNOWN_IDS)
    )
    records = tuple(_record(definition, configured_ids) for definition in sorted(_CATALOG, key=lambda item: item.id))
    document = CapabilityExport(
        schema_version=SCHEMA_VERSION,
        registry=REGISTRY_NAME,
        profile=profile_name,
        profile_valid=not profile_errors,
        profile_errors=profile_errors,
        capabilities=records,
    )
    return document.as_dict()
