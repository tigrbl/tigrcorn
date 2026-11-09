from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tigrcorn_core.errors import ProtocolError

from .metadata import UnitIdentity, asgi3_extensions
from .scopes import validate_scope

HTTPFeatureKind = Literal[
    "alt-svc",
    "content-coding",
    "early-hints",
    "proxy-normalization",
    "static-delivery",
    "trailers",
]

_HTTP_FEATURE_EVENTS = {
    "alt-svc": ("http.response.start",),
    "content-coding": ("http.response.start", "http.response.body"),
    "early-hints": ("http.response.start",),
    "proxy-normalization": ("http.request",),
    "static-delivery": ("http.response.pathsend", "http.response.body"),
    "trailers": ("http.request.trailers", "http.response.trailers"),
}


@dataclass(frozen=True, slots=True)
class CompatibilityParityRow:
    feature_id: str
    native_contract: bool
    asgi3_compat: bool
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "native_contract": self.native_contract,
            "asgi3_compat": self.asgi3_compat,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class HTTPFeatureContractMap:
    feature: HTTPFeatureKind
    contract_events: tuple[str, ...]
    asgi_extensions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "contract_events": list(self.contract_events),
            "asgi_extensions": list(self.asgi_extensions),
            "metadata": dict(self.metadata),
        }


def asgi3_compat_scope(scope: dict[str, Any], *, extensions: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_scope(scope)
    compat_scope = dict(scope)
    merged_extensions = dict(scope.get("extensions") or {})
    merged_extensions.update(extensions or {})
    merged_extensions.setdefault("tigrcorn.compat", {"interface": "asgi3", "native_contract": False})
    compat_scope["extensions"] = merged_extensions
    return compat_scope


def asgi_extension_bridge(
    *,
    unit: UnitIdentity | None = None,
    capabilities: dict[str, Any] | None = None,
    feature_maps: list[HTTPFeatureContractMap] | None = None,
    **extension_parts: Any,
) -> dict[str, Any]:
    bridge = asgi3_extensions(unit=unit, **extension_parts)
    bridge["tigrcorn.capabilities"] = dict(capabilities or {})
    bridge["tigrcorn.http_features"] = [item.as_dict() for item in feature_maps or []]
    return bridge


def compatibility_feature_parity(feature_id: str, *, native_contract: bool, asgi3_compat: bool, notes: str = "") -> CompatibilityParityRow:
    if not feature_id.startswith("feat:"):
        raise ProtocolError("compatibility parity rows require a feature id")
    return CompatibilityParityRow(
        feature_id=feature_id,
        native_contract=native_contract,
        asgi3_compat=asgi3_compat,
        notes=notes,
    )


def http_feature_contract_map(
    feature: str,
    *,
    asgi_extensions: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> HTTPFeatureContractMap:
    normalized = feature.strip().lower().replace("_", "-")
    if normalized not in _HTTP_FEATURE_EVENTS:
        raise ProtocolError(f"unsupported HTTP contract feature map: {feature!r}")
    return HTTPFeatureContractMap(
        feature=normalized,  # type: ignore[arg-type]
        contract_events=_HTTP_FEATURE_EVENTS[normalized],
        asgi_extensions=asgi_extensions,
        metadata=dict(metadata or {}),
    )


def alt_svc_contract_map(value: str, *, max_age: int | None = None, persist: bool = False) -> HTTPFeatureContractMap:
    if not value:
        raise ProtocolError("Alt-Svc contract map requires a header value")
    metadata: dict[str, Any] = {"header": value, "persist": persist}
    if max_age is not None:
        metadata["max_age"] = max_age
    return http_feature_contract_map("alt-svc", metadata=metadata)


def content_coding_contract_map(codings: tuple[str, ...]) -> HTTPFeatureContractMap:
    if not codings:
        raise ProtocolError("content-coding contract map requires at least one coding")
    return http_feature_contract_map("content-coding", metadata={"codings": list(codings)})


def early_hints_contract_map(headers: list[tuple[bytes, bytes]]) -> HTTPFeatureContractMap:
    if not headers:
        raise ProtocolError("early-hints contract map requires headers")
    return http_feature_contract_map("early-hints", metadata={"status": 103, "headers": headers})


def proxy_normalization_contract_map(*, trusted: bool, forwarded_for: str | None = None, scheme: str | None = None) -> HTTPFeatureContractMap:
    metadata = {"trusted": trusted}
    if forwarded_for is not None:
        metadata["forwarded_for"] = forwarded_for
    if scheme is not None:
        metadata["scheme"] = scheme
    return http_feature_contract_map("proxy-normalization", metadata=metadata)


def static_delivery_contract_map(path: str, *, pathsend: bool = True, range_request: bool = False, etag: str | None = None) -> HTTPFeatureContractMap:
    if not path.startswith("/"):
        raise ProtocolError("static delivery contract path must be absolute")
    metadata: dict[str, Any] = {"path": path, "pathsend": pathsend, "range_request": range_request}
    if etag is not None:
        metadata["etag"] = etag
    return http_feature_contract_map(
        "static-delivery",
        asgi_extensions=("http.response.pathsend",) if pathsend else (),
        metadata=metadata,
    )


def trailers_contract_map(*, request: bool = False, response: bool = False) -> HTTPFeatureContractMap:
    if not request and not response:
        raise ProtocolError("trailers contract map requires request or response trailers")
    extensions = []
    if request:
        extensions.append("tigrcorn.http.request_trailers")
    if response:
        extensions.append("http.response.trailers")
    return http_feature_contract_map("trailers", asgi_extensions=tuple(extensions), metadata={"request": request, "response": response})


def observability_contract_metadata(
    *,
    unit_id: str,
    feature_id: str,
    boundary_id: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not unit_id or not feature_id.startswith("feat:") or not boundary_id.startswith("bnd:"):
        raise ProtocolError("observability contract metadata requires unit, feature, and boundary ids")
    return {
        "tigrcorn.observability": {
            "unit_id": unit_id,
            "feature_id": feature_id,
            "boundary_id": boundary_id,
            "attributes": dict(attributes or {}),
        }
    }
