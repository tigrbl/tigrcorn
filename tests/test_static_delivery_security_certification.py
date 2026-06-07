from __future__ import annotations

import json
import os

import pytest

from tigrcorn.static import (
    StaticSecurityCertificationError,
    certify_static_delivery_security,
    static_alt_svc_headers,
    static_cache_headers,
    static_delivery_certification_artifact,
    static_security_policy,
    validate_static_early_hints,
    validate_static_path,
    validate_static_range_request,
    validate_static_resolved_path,
)


def test_static_security_policy_shape() -> None:
    policy = static_security_policy()

    assert policy["certification_id"] == "tigrcorn.static.security"
    assert policy["schema_version"] == 1
    assert policy["negative_corpus_required"] == (
        "dotdot_traversal",
        "encoded_traversal",
        "unicode_traversal",
        "symlink_escape",
    )
    assert policy["policy"] == {
        "allow_early_hints": True,
        "allow_static_alt_svc": False,
        "reject_dotdot": True,
        "reject_encoded_traversal": True,
        "reject_symlink_escape": True,
        "reject_unicode_traversal": True,
        "safe_cache_on_error": "no-store",
    }


def test_static_delivery_certification_artifact_shape() -> None:
    first = static_delivery_certification_artifact()
    second = static_delivery_certification_artifact()

    assert first == second
    assert first["artifact_id"] == "tigrcorn.static.delivery-security"
    assert first["schema_version"] == 1
    assert first["delivery_interactions"]["range"] == "after_path_policy"
    assert json.dumps(first, sort_keys=True)


def test_static_traversal_dotdot_rejected(tmp_path) -> None:
    root = tmp_path / "public"
    root.mkdir()

    with pytest.raises(StaticSecurityCertificationError, match="traversal"):
        validate_static_path(root, "/../secret.txt")


def test_static_symlink_escape_rejected(tmp_path) -> None:
    root = tmp_path / "public"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "escape.txt"
    if hasattr(os, "symlink"):
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            link = outside
    else:
        link = outside

    with pytest.raises(StaticSecurityCertificationError, match="escapes root"):
        if link == outside:
            validate_static_resolved_path(root, outside)
        else:
            validate_static_path(root, "/escape.txt")


def test_static_cache_poisoning_controls() -> None:
    unsafe = static_cache_headers(
        status=404,
        response_headers=[(b"cache-control", b"public, max-age=3600"), (b"set-cookie", b"a=b")],
    )
    safe = static_cache_headers(status=200, response_headers=[])

    assert unsafe == [(b"set-cookie", b"a=b"), (b"cache-control", b"no-store")]
    assert (b"cache-control", b"public, max-age=3600") in safe


def test_static_traversal_encoded_rejected(tmp_path) -> None:
    root = tmp_path / "public"
    root.mkdir()

    with pytest.raises(StaticSecurityCertificationError, match="traversal"):
        validate_static_path(root, "/%2e%2e/secret.txt")
    with pytest.raises(StaticSecurityCertificationError, match="traversal"):
        validate_static_path(root, "/%252e%252e/secret.txt")


def test_static_traversal_unicode_rejected(tmp_path) -> None:
    root = tmp_path / "public"
    root.mkdir()

    with pytest.raises(StaticSecurityCertificationError, match="traversal"):
        validate_static_path(root, "/\uff0e\uff0e/secret.txt")


def test_static_alt_svc_interaction() -> None:
    assert static_alt_svc_headers(
        profile="static-origin",
        static_enabled=True,
        requested_headers=[b'h3=":443"; ma=3600'],
    ) == []
    assert static_alt_svc_headers(
        profile="strict-h3-edge",
        static_enabled=True,
        requested_headers=[b'h3=":443"; ma=3600', b'h2=":443"'],
    ) == [(b"alt-svc", b'h3=":443"; ma=3600')]


def test_static_early_hints_validation() -> None:
    safe = validate_static_early_hints([(b"link", b"</assets/app.css>; rel=preload")])

    assert safe == [(b"link", b"</assets/app.css>; rel=preload")]
    with pytest.raises(StaticSecurityCertificationError, match="unsafe Early Hints path"):
        validate_static_early_hints([(b"link", b"</%2e%2e/secret.css>; rel=preload")])
    with pytest.raises(StaticSecurityCertificationError, match="unsafe Early Hints header"):
        validate_static_early_hints([(b"authorization", b"Bearer secret")])


def test_static_range_request_traversal_composition(tmp_path) -> None:
    root = tmp_path / "public"
    root.mkdir()
    (root / "asset.txt").write_text("hello", encoding="utf-8")

    accepted = validate_static_range_request(root, "/asset.txt", range_header=b"bytes=0-1")
    assert accepted == {
        "accepted": True,
        "path": "/asset.txt",
        "range": "bytes=0-1",
    }
    with pytest.raises(StaticSecurityCertificationError, match="traversal"):
        validate_static_range_request(root, "/../secret.txt", range_header=b"bytes=0-1")


def test_static_certification_fails_without_negative_corpus() -> None:
    with pytest.raises(StaticSecurityCertificationError, match="negative corpus"):
        certify_static_delivery_security({"policy": static_security_policy()["policy"]})

    result = certify_static_delivery_security(
        {
            "policy": static_security_policy()["policy"],
            "negative_corpus": {
                "dotdot_traversal": True,
                "encoded_traversal": True,
                "unicode_traversal": True,
                "symlink_escape": True,
            },
        }
    )
    assert result["certification_state"] == "certified"
