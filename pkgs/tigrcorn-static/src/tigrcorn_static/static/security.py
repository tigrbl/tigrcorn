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
