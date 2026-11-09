from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.x509 import ocsp

from tests.fixtures_pkg.interop_ocsp_fixtures import (
    CertificateFactory,
    ResponseSpec,
    der_ocsp,
    pem_certificate,
    revocation_http_server,
)
from tigrcorn.errors import ProtocolError
from tigrcorn.security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    RevocationFetchPolicy,
    RevocationMode,
    verify_certificate_chain,
)


def _trust_bundle(root, issuer) -> list[bytes]:
    return [pem_certificate(root), pem_certificate(issuer)]


def test_good_ocsp_response_is_cached_for_client_auth() -> None:
    factory = CertificateFactory()
    with revocation_http_server({}) as server:
        root, root_key = factory.make_ca('Root CA', path_length=1)
        issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
        leaf, _ = factory.make_client_leaf('client.good.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-good'),))
        server.responses[('POST', '/ocsp-good')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(leaf, issuer, issuer_key, next_update=datetime.now(timezone.utc) + timedelta(minutes=30))),
            headers={'Content-Type': 'application/ocsp-response', 'Cache-Control': 'max-age=600'},
        )
        policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        verified = verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=policy)
        assert verified.serial_number == leaf.serial_number
        assert server.count('POST', '/ocsp-good') == 1
        verified = verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=policy)
        assert verified.serial_number == leaf.serial_number
        assert server.count('POST', '/ocsp-good') == 1


def test_stale_ocsp_response_fails_in_require_mode() -> None:
    factory = CertificateFactory()
    with revocation_http_server({}) as server:
        root, root_key = factory.make_ca('Root CA', path_length=1)
        issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
        leaf, _ = factory.make_client_leaf('client.stale.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-stale'),))
        server.responses[('POST', '/ocsp-stale')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(leaf, issuer, issuer_key, next_update=datetime.now(timezone.utc) - timedelta(hours=1), this_update=datetime.now(timezone.utc) - timedelta(days=1))),
            headers={'Content-Type': 'application/ocsp-response'},
        )
        policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        with pytest.raises(ProtocolError, match='revocation status could not be established'):
            verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=policy)


def test_revoked_client_certificate_fails_in_require_mode() -> None:
    factory = CertificateFactory()
    with revocation_http_server({}) as server:
        root, root_key = factory.make_ca('Root CA', path_length=1)
        issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
        leaf, _ = factory.make_client_leaf('client.revoked.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-revoked'),))
        server.responses[('POST', '/ocsp-revoked')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(leaf, issuer, issuer_key, cert_status=ocsp.OCSPCertStatus.REVOKED, next_update=datetime.now(timezone.utc) + timedelta(minutes=30))),
            headers={'Content-Type': 'application/ocsp-response'},
        )
        policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        with pytest.raises(ProtocolError, match='revoked'):
            verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=policy)


def test_unreachable_responder_soft_fail_and_require_modes_diverge() -> None:
    factory = CertificateFactory()
    root, root_key = factory.make_ca('Root CA', path_length=1)
    issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
    leaf, _ = factory.make_client_leaf('client.unreachable.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=('http://127.0.0.1:9/unreachable',))
    soft_policy = CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=RevocationMode.SOFT_FAIL,
        revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
    )
    require_policy = CertificateValidationPolicy(
        purpose=CertificatePurpose.CLIENT_AUTH,
        revocation_mode=RevocationMode.REQUIRE,
        revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
    )
    verified = verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=soft_policy)
    assert verified.serial_number == leaf.serial_number
    with pytest.raises(ProtocolError, match='OCSP http://127.0.0.1:9/unreachable'):
        verify_certificate_chain([pem_certificate(leaf), pem_certificate(issuer)], _trust_bundle(root, issuer), policy=require_policy)
