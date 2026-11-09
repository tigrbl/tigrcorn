from __future__ import annotations

import json

from tigrcorn_certification.hardening_suites import (
    export_hardening_suite_catalog,
    validate_hardening_suite_catalog,
)


def test_hardening_suite_catalog_assigns_package_owners() -> None:
    payload = export_hardening_suite_catalog()
    catalog = payload["catalog"]

    assert payload["schema_version"] == 1
    assert validate_hardening_suite_catalog(catalog)["passed"] is True
    assert catalog["http1"]["owner_package"] == "tigrcorn-protocols"
    assert catalog["http2"]["owner_package"] == "tigrcorn-protocols"
    assert catalog["http3_quic"]["owner_package"] == "tigrcorn-transports"
    assert catalog["static"]["owner_package"] == "tigrcorn-static"
    assert catalog["certification"]["owner_package"] == "tigrcorn-certification"


def test_hardening_suite_catalog_declares_test_ownership() -> None:
    catalog = export_hardening_suite_catalog()["catalog"]

    for suite in catalog.values():
        assert suite["package_tests"]
        assert suite["cross_cutting_tests"]
        assert all(path.startswith("tests/") for path in suite["package_tests"])
        assert all(path.startswith("tests/") for path in suite["cross_cutting_tests"])


def test_hardening_suite_catalog_excludes_unscoped_boundary_expansions() -> None:
    text = json.dumps(export_hardening_suite_catalog(), sort_keys=True).lower()

    assert "dtls" not in text
    assert "rfc 9147" not in text
    assert "http/2 proxy" not in text
    assert "proxying" not in text

