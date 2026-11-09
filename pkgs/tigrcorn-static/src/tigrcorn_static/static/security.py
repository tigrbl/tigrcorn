from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import unquote

from tigrcorn_core.utils.headers import append_if_missing, get_header

from .models import HeaderList, StaticPathDecision


class StaticSecurityCertificationError(ValueError):
    """Raised when static-delivery security certification fails closed."""


@dataclass(frozen=True, slots=True)
class StaticSecurityPolicy:
    reject_dotdot: bool = True
    reject_encoded_traversal: bool = True
    reject_unicode_traversal: bool = True
    reject_symlink_escape: bool = True
    safe_cache_on_error: str = "no-store"
    allow_static_alt_svc: bool = False
    allow_early_hints: bool = True

    def as_dict(self) -> dict[str, bool | str]:
        return {
            "allow_early_hints": self.allow_early_hints,
            "allow_static_alt_svc": self.allow_static_alt_svc,
            "reject_dotdot": self.reject_dotdot,
            "reject_encoded_traversal": self.reject_encoded_traversal,
            "reject_symlink_escape": self.reject_symlink_escape,
            "reject_unicode_traversal": self.reject_unicode_traversal,
            "safe_cache_on_error": self.safe_cache_on_error,
        }


def static_security_policy() -> dict[str, Any]:
    policy = StaticSecurityPolicy()
    return {
        "certification_id": "tigrcorn.static.security",
        "negative_corpus_required": (
            "dotdot_traversal",
            "encoded_traversal",
            "unicode_traversal",
            "symlink_escape",
        ),
        "policy": policy.as_dict(),
        "schema_version": 1,
    }


def static_delivery_certification_artifact() -> dict[str, Any]:
    return {
        "artifact_id": "tigrcorn.static.delivery-security",
        "cache_poisoning": {"unsafe_responses": "no-store"},
        "certification": {
            "required_negative_corpus": (
                "dotdot_traversal",
                "encoded_traversal",
                "unicode_traversal",
                "symlink_escape",
            ),
            "state": "uncertified",
        },
        "delivery_interactions": {
            "alt_svc": "disabled_for_static_unless_explicitly_safe",
            "early_hints": "validated_link_headers_only",
            "range": "after_path_policy",
        },
        "path_policy": static_security_policy()["policy"],
        "schema_version": 1,
    }


def build_static_certification_evidence(root: str | Path, *, profile: str = "default") -> dict[str, Any]:
    root_path = Path(root)
    negative_corpus = {
        "dotdot_traversal": _raises_static_error(lambda: validate_static_path(root_path, "/../secret.txt")),
        "encoded_traversal": _raises_static_error(lambda: validate_static_path(root_path, "/%2e%2e/secret.txt")),
        "unicode_traversal": _raises_static_error(lambda: validate_static_path(root_path, "/\uff0e\uff0e/secret.txt")),
        "symlink_escape": _raises_static_error(lambda: validate_static_resolved_path(root_path, root_path.parent / "__tigrcorn_escape_probe__")),
    }
    alt_svc_headers = static_alt_svc_headers(
        profile=profile,
        static_enabled=True,
        requested_headers=[b'h3=":443"; ma=3600', b'h2=":443"'],
    )
    early_hints = validate_static_early_hints([(b"link", b"</assets/app.css>; rel=preload")])
    return {
        "checks": {
            "alt_svc": _json_header_list(alt_svc_headers),
            "early_hints": _json_header_list(early_hints),
            "range_amplification": validate_static_range_amplification(b"bytes=0-0", resource_length=1),
        },
        "mount_name": root_path.name,
        "negative_corpus": negative_corpus,
        "policy": static_security_policy()["policy"],
        "profile": profile,
        "schema_version": 1,
    }


def validate_static_path(root: str | Path, request_path: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    decoded = _decode_static_path(request_path)
    normalized = unicodedata.normalize("NFKC", decoded)
    decision = _validate_static_path_parts(normalized)
    if not decision.accepted:
        raise StaticSecurityCertificationError(decision.reason)
    candidate = root_path.joinpath(*PurePosixPath(normalized).parts[1:]).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise StaticSecurityCertificationError("static path escapes root") from exc
    return {
        "accepted": True,
        "normalized_path": "/" + "/".join(candidate.relative_to(root_path).parts),
        "resolved_path": os.fspath(candidate),
    }


def validate_static_resolved_path(root: str | Path, resolved_candidate: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate = Path(resolved_candidate).resolve()
    try:
        relative = candidate.relative_to(root_path)
    except ValueError as exc:
        raise StaticSecurityCertificationError("static path escapes root") from exc
    return {
        "accepted": True,
        "normalized_path": "/" + "/".join(relative.parts),
        "resolved_path": os.fspath(candidate),
    }


def static_cache_headers(
    *,
    status: int,
    method: str = "GET",
    response_headers: Iterable[tuple[bytes | str, bytes | str]] = (),
) -> list[tuple[bytes, bytes]]:
    headers = [
        (
            name if isinstance(name, bytes) else str(name).encode("latin1"),
            value if isinstance(value, bytes) else str(value).encode("latin1"),
        )
        for name, value in response_headers
    ]
    unsafe = (
        method.upper() not in {"GET", "HEAD"}
        or status >= 400
        or get_header([(name.lower(), value) for name, value in headers], b"set-cookie") is not None
    )
    if unsafe:
        return _without_header(headers, b"cache-control") + [(b"cache-control", b"no-store")]
    append_if_missing(headers, b"cache-control", b"public, max-age=3600")
    return headers


def static_alt_svc_headers(
    *,
    profile: str,
    static_enabled: bool,
    requested_headers: Iterable[bytes | str] = (),
) -> list[tuple[bytes, bytes]]:
    if not static_enabled or profile in {"static-origin", "default", "strict-h1-origin"}:
        return []
    headers = [
        value if isinstance(value, bytes) else str(value).encode("latin1")
        for value in requested_headers
    ]
    return [(b"alt-svc", value) for value in headers if b"h3=" in value.lower()]


def validate_static_early_hints(
    headers: Iterable[tuple[bytes | str, bytes | str]],
) -> list[tuple[bytes, bytes]]:
    safe: list[tuple[bytes, bytes]] = []
    for raw_name, raw_value in headers:
        name = raw_name if isinstance(raw_name, bytes) else str(raw_name).encode("latin1")
        value = raw_value if isinstance(raw_value, bytes) else str(raw_value).encode("latin1")
        lowered = name.lower()
        if lowered != b"link":
            raise StaticSecurityCertificationError("unsafe Early Hints header")
        decoded = unquote(value.decode("latin1", "ignore"))
        if ".." in unicodedata.normalize("NFKC", decoded) or "\\" in decoded:
            raise StaticSecurityCertificationError("unsafe Early Hints path")
        safe.append((b"link", value))
    return safe


def validate_static_range_request(
    root: str | Path,
    request_path: str,
    *,
    range_header: bytes | str,
) -> dict[str, Any]:
    path_decision = validate_static_path(root, request_path)
    header_value = range_header if isinstance(range_header, bytes) else str(range_header).encode("latin1")
    if not header_value.lower().startswith(b"bytes="):
        raise StaticSecurityCertificationError("unsupported static range unit")
    return {
        "accepted": True,
        "path": path_decision["normalized_path"],
        "range": header_value.decode("latin1"),
    }


def validate_static_sidecar_pair(
    origin: str | Path,
    sidecar: str | Path,
    *,
    coding: str,
) -> dict[str, Any]:
    origin_path = Path(origin)
    sidecar_path = Path(sidecar)
    expected_suffix = _sidecar_suffix_map().get(coding)
    if expected_suffix is None:
        raise StaticSecurityCertificationError(f"unsupported static sidecar coding: {coding}")
    if sidecar_path.name != origin_path.name + expected_suffix:
        raise StaticSecurityCertificationError("static sidecar name does not match origin")
    if not origin_path.exists() or not sidecar_path.exists():
        raise StaticSecurityCertificationError("static sidecar pair is incomplete")
    return {
        "accepted": True,
        "coding": coding,
        "origin": os.fspath(origin_path),
        "sidecar": os.fspath(sidecar_path),
        "sidecar_size": sidecar_path.stat().st_size,
    }


def validate_static_content_length(
    headers: Iterable[tuple[bytes | str, bytes | str]],
    *,
    expected_length: int,
) -> dict[str, Any]:
    normalized = [
        (
            name if isinstance(name, bytes) else str(name).encode("latin1"),
            value if isinstance(value, bytes) else str(value).encode("latin1"),
        )
        for name, value in headers
    ]
    value = get_header([(name.lower(), header_value) for name, header_value in normalized], b"content-length")
    if value is None:
        return {"accepted": True, "content_length": None}
    try:
        parsed = int(value.decode("ascii"))
    except ValueError as exc:
        raise StaticSecurityCertificationError("invalid static content-length") from exc
    if parsed != expected_length:
        raise StaticSecurityCertificationError("static content-length mismatch")
    return {"accepted": True, "content_length": parsed}


def validate_static_range_amplification(
    range_header: bytes | str,
    *,
    resource_length: int,
    max_parts: int = 16,
) -> dict[str, Any]:
    value = range_header if isinstance(range_header, bytes) else str(range_header).encode("latin1")
    if not value.lower().startswith(b"bytes="):
        raise StaticSecurityCertificationError("unsupported static range unit")
    parts = [part.strip() for part in value[6:].split(b",") if part.strip()]
    if len(parts) > max_parts:
        raise StaticSecurityCertificationError("static range amplification limit exceeded")
    if resource_length < 0:
        raise StaticSecurityCertificationError("invalid static resource length")
    return {"accepted": True, "parts": len(parts), "resource_length": resource_length}


def certify_static_delivery_security(evidence: Mapping[str, Any]) -> dict[str, Any]:
    corpus = evidence.get("negative_corpus") or {}
    required = ("dotdot_traversal", "encoded_traversal", "unicode_traversal", "symlink_escape")
    missing = tuple(key for key in required if not corpus.get(key))
    if missing:
        raise StaticSecurityCertificationError(
            "missing static negative corpus: " + ", ".join(missing)
        )
    return {
        "certification_state": "certified",
        "negative_corpus": required,
        "evidence_keys": tuple(sorted(evidence)),
    }


def _decode_static_path(request_path: str) -> str:
    decoded = str(request_path or "/")
    for _ in range(3):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return decoded


def _validate_static_path_parts(path: str) -> StaticPathDecision:
    if "\x00" in path:
        return StaticPathDecision(False, None, "static path contains NUL")
    parts: list[str] = []
    for part in PurePosixPath(path).parts:
        if part in {"", "/", "."}:
            continue
        normalized_part = unicodedata.normalize("NFKC", part)
        if normalized_part == "..":
            return StaticPathDecision(False, None, "static traversal rejected")
        if "\\" in normalized_part or "/" in normalized_part:
            return StaticPathDecision(False, None, "static path separator rejected")
        parts.append(normalized_part)
    return StaticPathDecision(True, "/" + "/".join(parts), "accepted")


def _without_header(headers: HeaderList, name: bytes) -> HeaderList:
    lowered = name.lower()
    return [(header_name, value) for header_name, value in headers if header_name.lower() != lowered]


def _raises_static_error(callback) -> bool:
    try:
        callback()
    except StaticSecurityCertificationError:
        return True
    return False


def _sidecar_suffix_map() -> dict[str, str]:
    return {"br": ".br", "gzip": ".gz"}


def _json_header_list(headers: Iterable[tuple[bytes, bytes]]) -> list[list[str]]:
    return [[name.decode("latin1"), value.decode("latin1")] for name, value in headers]
