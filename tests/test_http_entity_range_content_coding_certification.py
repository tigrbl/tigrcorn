from __future__ import annotations

import gzip
import json
import zlib

import pytest

from tigrcorn.http.certification import (
    HttpCertificationError,
    HttpCertificationPolicy,
    certify_http_entity_range_content_coding,
    conditional_request_result,
    content_coding_policy_result,
    decode_content_coding,
    http_certification_artifact,
    http_certification_surface,
    if_range_result,
    reject_malformed_range,
    strong_validator_result,
    validate_range_amplification,
    weak_validator_result,
)


def test_http_certification_surface_shape() -> None:
    surface = http_certification_surface()

    assert surface == {
        "certification_id": "tigrcorn.http.entity-range-content-coding",
        "sections": ("etag", "conditional", "range", "content_coding", "negative_corpus"),
        "schema_version": 1,
        "surface": "tigrcorn.http.certification",
    }


def test_http_certification_artifact_deterministic() -> None:
    first = http_certification_artifact()
    second = http_certification_artifact()

    assert first == second
    assert first["etag"]["weak_validator"] == "semantic-match"
    assert first["range"]["overlap_amplification"] == "bounded"
    assert first["content_coding"]["malformed_streams"] == "reject"
    assert json.dumps(first, sort_keys=True)


def test_http_etag_weak_validator() -> None:
    weak = weak_validator_result(b'W/"abc"', b'"abc"')

    assert weak["weak_match"] is True
    assert weak["strong_match"] is False


def test_http_etag_strong_validator() -> None:
    strong = strong_validator_result(b'"abc"', b'"abc"')
    weak_candidate = strong_validator_result(b'"abc"', b'W/"abc"')

    assert strong["strong_match"] is True
    assert strong["weak_match"] is True
    assert weak_candidate["strong_match"] is False
    assert weak_candidate["weak_match"] is True


def test_http_conditional_request_semantics() -> None:
    not_modified = conditional_request_result(
        method="GET",
        request_headers=[(b"if-none-match", b'W/"abc"')],
        etag=b'"abc"',
    )
    precondition_failed = conditional_request_result(
        method="PUT",
        request_headers=[(b"if-match", b'"other"')],
        etag=b'"abc"',
    )

    assert not_modified["status"] == 304
    assert not_modified["not_modified"] is True
    assert not_modified["body_length"] == 0
    assert precondition_failed["status"] == 412
    assert precondition_failed["precondition_failed"] is True


def test_http_content_coding_policy() -> None:
    allowed = content_coding_policy_result(accept_encoding=b"gzip", policy="allowlist")
    identity = content_coding_policy_result(accept_encoding=b"gzip", policy="identity-only")
    strict_blocked = content_coding_policy_result(accept_encoding=b"zstd", policy="strict")

    assert allowed["status"] == 200
    assert allowed["coding"] == "gzip"
    assert allowed["content_encoding"] == "gzip"
    assert identity["status"] == 200
    assert identity["content_encoding"] is None
    assert strict_blocked["status"] == 406


def test_http_range_malformed_rejected() -> None:
    assert reject_malformed_range(b"bytes=a-b") == {
        "accepted": False,
        "reason": "malformed_range",
    }
    with pytest.raises(HttpCertificationError, match="accepted"):
        reject_malformed_range(b"bytes=0-1")


def test_http_range_overlap_and_amplification() -> None:
    accepted = validate_range_amplification(
        b"bytes=0-9,10-19",
        resource_length=100,
        policy=HttpCertificationPolicy(max_ranges=4, max_range_amplification=1.0),
    )

    assert accepted["accepted"] is True
    assert accepted["amplification"] == 1.0
    with pytest.raises(HttpCertificationError, match="amplification"):
        validate_range_amplification(
            b"bytes=0-99,0-99,0-99",
            resource_length=100,
            policy=HttpCertificationPolicy(max_ranges=4, max_range_amplification=2.0),
        )


def test_http_content_coding_malformed_stream() -> None:
    with pytest.raises(HttpCertificationError, match="malformed"):
        decode_content_coding("gzip", b"not-gzip")
    with pytest.raises(HttpCertificationError, match="malformed"):
        decode_content_coding("deflate", b"not-deflate")


def test_http_decompression_amplification_control() -> None:
    payload = gzip.compress(b"a" * 4096)
    policy = HttpCertificationPolicy(max_decompressed_bytes=10_000, max_decompression_ratio=1.5)

    with pytest.raises(HttpCertificationError, match="amplification"):
        decode_content_coding("gzip", payload, policy=policy)

    accepted = decode_content_coding(
        "deflate",
        zlib.compress(b"small"),
        policy=HttpCertificationPolicy(max_decompressed_bytes=100, max_decompression_ratio=10.0),
    )
    assert accepted["accepted"] is True
    assert accepted["decoded_bytes"] == 5


def test_http_if_range_stale_validator_rejected() -> None:
    stale = if_range_result(if_range=b'"stale"', current_etag=b'"fresh"')
    fresh = if_range_result(if_range=b'"fresh"', current_etag=b'"fresh"')

    assert stale["status"] == 200
    assert stale["applied"] is False
    assert stale["body"] == b"0123456789"
    assert fresh["status"] == 206
    assert fresh["applied"] is True
    assert fresh["body"] == b"01"


def test_http_certification_fails_without_negative_range_corpus() -> None:
    with pytest.raises(HttpCertificationError, match="negative range/coding corpus"):
        certify_http_entity_range_content_coding({"surface": http_certification_surface()})

    result = certify_http_entity_range_content_coding(
        {
            "surface": http_certification_surface(),
            "negative_corpus": {
                "malformed_range": True,
                "overlap_range": True,
                "malformed_coding": True,
                "decompression_amplification": True,
                "stale_if_range": True,
            },
        }
    )
    assert result["certification_state"] == "certified"
