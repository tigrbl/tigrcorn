from __future__ import annotations

import gzip
import zlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from tigrcorn_core.utils.headers import get_header
from tigrcorn_http.conditional import apply_conditional_request
from tigrcorn_http.etag import format_etag, parse_entity_tag, strong_compare, weak_compare
from tigrcorn_http.range import ByteRange, apply_byte_ranges, parse_range_header
from tigrcorn_protocols.content_coding import apply_http_content_coding


class HttpCertificationError(ValueError):
    """Raised when HTTP entity/range/content-coding certification fails closed."""


@dataclass(frozen=True, slots=True)
class HttpCertificationPolicy:
    max_ranges: int = 8
    max_range_amplification: float = 2.0
    max_decompression_ratio: float = 16.0
    max_decompressed_bytes: int = 1_048_576
    supported_codings: tuple[str, ...] = ("gzip", "deflate", "br")

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_decompressed_bytes": self.max_decompressed_bytes,
            "max_decompression_ratio": self.max_decompression_ratio,
            "max_range_amplification": self.max_range_amplification,
            "max_ranges": self.max_ranges,
            "supported_codings": self.supported_codings,
        }


def http_certification_surface() -> dict[str, Any]:
    return {
        "certification_id": "tigrcorn.http.entity-range-content-coding",
        "sections": ("etag", "conditional", "range", "content_coding", "negative_corpus"),
        "schema_version": 1,
        "surface": "tigrcorn.http.certification",
    }


def http_certification_artifact(policy: HttpCertificationPolicy | None = None) -> dict[str, Any]:
    selected = HttpCertificationPolicy() if policy is None else policy
    return {
        "artifact_id": "tigrcorn.http.entity-range-content-coding",
        "content_coding": {
            "malformed_streams": "reject",
            "policy": selected.as_dict(),
        },
        "etag": {
            "strong_validator": "byte-identical-only",
            "weak_validator": "semantic-match",
        },
        "negative_corpus_required": (
            "malformed_range",
            "overlap_range",
            "malformed_coding",
            "decompression_amplification",
            "stale_if_range",
        ),
        "range": {
            "malformed": "reject",
            "overlap_amplification": "bounded",
        },
        "schema_version": 1,
    }


def weak_validator_result(current: bytes | str, candidate: bytes | str) -> dict[str, Any]:
    left = parse_entity_tag(current)
    right = parse_entity_tag(candidate)
    return {
        "candidate": _safe_etag(candidate),
        "current": _safe_etag(current),
        "strong_match": strong_compare(left, right),
        "weak_match": weak_compare(left, right),
    }


def strong_validator_result(current: bytes | str, candidate: bytes | str) -> dict[str, Any]:
    left = parse_entity_tag(current)
    right = parse_entity_tag(candidate)
    return {
        "candidate": _safe_etag(candidate),
        "current": _safe_etag(current),
        "strong_match": strong_compare(left, right),
        "weak_match": weak_compare(left, right),
    }


def conditional_request_result(
    *,
    method: str,
    request_headers: Iterable[tuple[bytes, bytes]],
    etag: bytes = b'"abc"',
    body: bytes = b"payload",
) -> dict[str, Any]:
    result = apply_conditional_request(
        method=method,
        request_headers=tuple(request_headers),
        response_headers=[(b"etag", etag), (b"last-modified", b"Sun, 01 Jan 2023 00:00:00 GMT")],
        body=body,
        status=200,
    )
    return {
        "body_length": len(result.body),
        "not_modified": result.not_modified,
        "precondition_failed": result.precondition_failed,
        "status": result.status,
    }


def content_coding_policy_result(
    *,
    accept_encoding: bytes,
    policy: str,
    supported: tuple[str, ...] = ("gzip", "deflate"),
) -> dict[str, Any]:
    status, headers, body, selection = apply_http_content_coding(
        request_headers=[(b"accept-encoding", accept_encoding)],
        response_headers=[(b"content-type", b"text/plain")],
        body=b"compress-me",
        status=200,
        policy=policy,
        supported=supported,
    )
    return {
        "coding": selection.coding,
        "content_encoding": _decode_header(get_header(headers, b"content-encoding")),
        "identity_acceptable": selection.identity_acceptable,
        "status": status,
        "body_length": len(body),
    }


def reject_malformed_range(range_header: bytes | str, *, resource_length: int = 100) -> dict[str, Any]:
    parsed = parse_range_header(range_header, resource_length=resource_length)
    if parsed is not None:
        raise HttpCertificationError("malformed range was accepted")
    return {"accepted": False, "reason": "malformed_range"}


def validate_range_amplification(
    range_header: bytes | str,
    *,
    resource_length: int,
    policy: HttpCertificationPolicy | None = None,
) -> dict[str, Any]:
    selected = HttpCertificationPolicy() if policy is None else policy
    ranges = parse_range_header(range_header, resource_length=resource_length)
    if ranges is None or ranges == []:
        raise HttpCertificationError("range set is malformed or unsatisfied")
    requested = sum(item.end - item.start + 1 for item in ranges)
    unique = _unique_range_bytes(ranges)
    amplification = float(requested) / float(max(unique, 1))
    if len(ranges) > selected.max_ranges or amplification > selected.max_range_amplification:
        raise HttpCertificationError("range overlap/amplification rejected")
    return {
        "accepted": True,
        "amplification": amplification,
        "range_count": len(ranges),
        "requested_bytes": requested,
        "unique_bytes": unique,
    }


def decode_content_coding(
    coding: str,
    payload: bytes,
    *,
    policy: HttpCertificationPolicy | None = None,
) -> dict[str, Any]:
    selected = HttpCertificationPolicy() if policy is None else policy
    try:
        if coding == "gzip":
            decoded = gzip.decompress(payload)
        elif coding == "deflate":
            decoded = zlib.decompress(payload)
        else:
            raise HttpCertificationError(f"unsupported content coding: {coding}")
    except (OSError, zlib.error) as exc:
        raise HttpCertificationError("malformed compressed stream rejected") from exc
    ratio = float(len(decoded)) / float(max(len(payload), 1))
    if len(decoded) > selected.max_decompressed_bytes or ratio > selected.max_decompression_ratio:
        raise HttpCertificationError("decompression amplification rejected")
    return {
        "accepted": True,
        "decoded_bytes": len(decoded),
        "encoded_bytes": len(payload),
        "ratio": ratio,
    }


def if_range_result(
    *,
    if_range: bytes,
    current_etag: bytes = b'"fresh"',
    body: bytes = b"0123456789",
) -> dict[str, Any]:
    result = apply_byte_ranges(
        method="GET",
        request_headers=[(b"range", b"bytes=0-1"), (b"if-range", if_range)],
        response_headers=[(b"etag", current_etag)],
        body=body,
        status=200,
    )
    return {
        "applied": result.applied,
        "body": result.body,
        "status": result.status,
    }


def certify_http_entity_range_content_coding(evidence: Mapping[str, Any]) -> dict[str, Any]:
    corpus = evidence.get("negative_corpus") or {}
    required = (
        "malformed_range",
        "overlap_range",
        "malformed_coding",
        "decompression_amplification",
        "stale_if_range",
    )
    missing = tuple(key for key in required if not corpus.get(key))
    if missing:
        raise HttpCertificationError(
            "missing HTTP negative range/coding corpus: " + ", ".join(missing)
        )
    return {
        "certification_state": "certified",
        "evidence_keys": tuple(sorted(evidence)),
        "negative_corpus": required,
    }


def _safe_etag(value: bytes | str) -> str:
    raw = value.decode("latin1") if isinstance(value, bytes) else str(value)
    return raw


def _decode_header(value: bytes | None) -> str | None:
    return None if value is None else value.decode("latin1")


def _unique_range_bytes(ranges: list[ByteRange]) -> int:
    covered: set[int] = set()
    for item in ranges:
        covered.update(range(item.start, item.end + 1))
    return len(covered)


__all__ = [
    "HttpCertificationError",
    "HttpCertificationPolicy",
    "certify_http_entity_range_content_coding",
    "conditional_request_result",
    "content_coding_policy_result",
    "decode_content_coding",
    "http_certification_artifact",
    "http_certification_surface",
    "if_range_result",
    "reject_malformed_range",
    "strong_validator_result",
    "validate_range_amplification",
    "weak_validator_result",
]
