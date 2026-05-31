from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tigrcorn_core.errors import ProtocolError

EndpointKind = Literal["tcp", "uds", "fd", "pipe", "inproc"]
IdentityKind = Literal["tcp", "unix", "quic", "http2", "http3", "webtransport-session", "webtransport-stream", "datagram"]


@dataclass(frozen=True, slots=True)
class EndpointMetadata:
    kind: EndpointKind
    address: str | None = None
    port: int | None = None
    fd: int | None = None
    pipe_name: str | None = None
    inproc_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "kind": self.kind,
            "address": self.address,
            "port": self.port,
            "fd": self.fd,
            "pipe_name": self.pipe_name,
            "inproc_name": self.inproc_name,
        }.items() if value is not None}


@dataclass(frozen=True, slots=True)
class ConnectionIdentity:
    kind: IdentityKind
    connection_id: str
    peer: str | None = None
    local: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = {"kind": self.kind, "connection_id": self.connection_id, **self.metadata}
        if self.peer is not None:
            payload["peer"] = self.peer
        if self.local is not None:
            payload["local"] = self.local
        return payload


@dataclass(frozen=True, slots=True)
class StreamIdentity:
    kind: IdentityKind
    connection_id: str
    stream_id: str
    session_id: str | None = None
    datagram_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {"kind": self.kind, "connection_id": self.connection_id, "stream_id": self.stream_id}
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.datagram_id is not None:
            payload["datagram_id"] = self.datagram_id
        return payload


@dataclass(frozen=True, slots=True)
class UnitIdentity:
    unit_id: str
    family: str
    binding: str
    connection_id: str | None = None
    stream_id: str | None = None
    session_id: str | None = None
    datagram_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {"unit_id": self.unit_id, "family": self.family, "binding": self.binding}
        for key in ("connection_id", "stream_id", "session_id", "datagram_id"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True, slots=True)
class SecurityMetadata:
    tls: bool = False
    mtls: bool = False
    alpn: str | None = None
    sni: str | None = None
    peer_certificate: str | None = None
    ocsp_status: str | None = None
    crl_status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in {
            "tls": self.tls,
            "mtls": self.mtls,
            "alpn": self.alpn,
            "sni": self.sni,
            "peer_certificate": self.peer_certificate,
            "ocsp_status": self.ocsp_status,
            "crl_status": self.crl_status,
        }.items() if value not in (None, False)}


def endpoint_metadata(kind: str, **fields: Any) -> EndpointMetadata:
    try:
        endpoint_kind = kind.strip().lower()  # type: ignore[assignment]
    except AttributeError as exc:
        raise ProtocolError("endpoint kind must be a string") from exc
    if endpoint_kind not in {"tcp", "uds", "fd", "pipe", "inproc"}:
        raise ProtocolError(f"unsupported endpoint kind: {kind!r}")
    metadata = EndpointMetadata(kind=endpoint_kind, **fields)  # type: ignore[arg-type]
    validate_endpoint_metadata(metadata)
    return metadata


def validate_endpoint_metadata(metadata: EndpointMetadata) -> None:
    if metadata.kind == "tcp" and (not metadata.address or metadata.port is None):
        raise ProtocolError("tcp endpoint metadata requires address and port")
    if metadata.kind == "uds" and not metadata.address:
        raise ProtocolError("uds endpoint metadata requires socket path")
    if metadata.kind == "fd" and metadata.fd is None:
        raise ProtocolError("fd endpoint metadata requires fd")
    if metadata.kind == "pipe" and not metadata.pipe_name:
        raise ProtocolError("pipe endpoint metadata requires pipe_name")
    if metadata.kind == "inproc" and not metadata.inproc_name:
        raise ProtocolError("inproc endpoint metadata requires inproc_name")


def transport_identity(kind: str, connection_id: str, **fields: Any) -> ConnectionIdentity:
    normalized = kind.strip().lower()
    if normalized not in {"tcp", "unix", "quic"}:
        raise ProtocolError(f"unsupported connection identity kind: {kind!r}")
    if not connection_id:
        raise ProtocolError("connection identity requires connection_id")
    return ConnectionIdentity(kind=normalized, connection_id=connection_id, **fields)  # type: ignore[arg-type]


def stream_identity(kind: str, connection_id: str, stream_id: str, **fields: Any) -> StreamIdentity:
    normalized = kind.strip().lower()
    if normalized not in {"http2", "http3", "webtransport-session", "webtransport-stream"}:
        raise ProtocolError(f"unsupported stream identity kind: {kind!r}")
    if not connection_id or not stream_id:
        raise ProtocolError("stream identity requires connection_id and stream_id")
    return StreamIdentity(kind=normalized, connection_id=connection_id, stream_id=stream_id, **fields)  # type: ignore[arg-type]


def datagram_identity(connection_id: str, datagram_id: str, *, session_id: str | None = None) -> StreamIdentity:
    if not connection_id or not datagram_id:
        raise ProtocolError("datagram identity requires connection_id and datagram_id")
    return StreamIdentity(kind="datagram", connection_id=connection_id, stream_id=datagram_id, datagram_id=datagram_id, session_id=session_id)


def unit_identity(unit_id: str, *, family: str, binding: str, **fields: Any) -> UnitIdentity:
    if not unit_id:
        raise ProtocolError("unit identity requires unit_id")
    normalized_family = family.strip().lower()
    if normalized_family not in {"request", "session", "message", "stream", "datagram"}:
        raise ProtocolError(f"unsupported unit family: {family!r}")
    normalized_binding = binding.strip().lower()
    if normalized_binding not in {"http", "http.stream", "websocket", "lifespan", "webtransport", "stream", "datagram"}:
        raise ProtocolError(f"unsupported unit binding: {binding!r}")
    return UnitIdentity(unit_id=unit_id, family=normalized_family, binding=normalized_binding, **fields)


def security_metadata(**fields: Any) -> SecurityMetadata:
    metadata = SecurityMetadata(**fields)
    if metadata.mtls and not metadata.tls:
        raise ProtocolError("mTLS metadata requires TLS metadata")
    return metadata


def require_lossless_metadata(name: str, value: Any) -> Any:
    if value in (None, "", (), [], {}):
        raise ProtocolError(f"required metadata would be lossy: {name}")
    return value


def asgi3_extensions(
    *,
    endpoint: EndpointMetadata | None = None,
    transport: ConnectionIdentity | StreamIdentity | None = None,
    security: SecurityMetadata | None = None,
    stream: StreamIdentity | None = None,
    datagram: StreamIdentity | None = None,
    completion: dict[str, Any] | None = None,
    unit: UnitIdentity | None = None,
) -> dict[str, Any]:
    extensions: dict[str, Any] = {}
    if endpoint is not None:
        extensions["tigrcorn.endpoint"] = endpoint.as_dict()
    if transport is not None:
        extensions["tigrcorn.transport"] = transport.as_dict()
    if security is not None:
        extensions["tigrcorn.security"] = security.as_dict()
    if stream is not None:
        extensions["tigrcorn.stream"] = stream.as_dict()
    if datagram is not None:
        extensions["tigrcorn.datagram"] = datagram.as_dict()
    if completion is not None:
        extensions["tigrcorn.emit_completion"] = completion
    if unit is not None:
        extensions["tigrcorn.unit"] = unit.as_dict()
    return extensions
