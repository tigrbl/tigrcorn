from __future__ import annotations

from datetime import timedelta

import pytest
from cryptography import x509
from cryptography.x509 import ocsp

from tigrcorn.errors import ProtocolError
from tigrcorn.security.tls import (
    CertificateValidationPolicy,
    RevocationFetchPolicy,
    RevocationMaterial,
    RevocationMode,
    verify_certificate_chain,
)
from tigrcorn.transports.quic.handshake import generate_self_signed_certificate
from tests.support.x509_webpki import (
    _NOW,
    _ResponseSpec,
    CertificateFactory,
    _der_crl,
    _der_ocsp,
    _pem,
    revocation_http_server,
)


class TestWebPkiValidator:
    def test_accepts_directly_trusted_self_signed_leaf_with_san_and_key_identifiers(self) -> None:
        cert_pem, _key_pem = generate_self_signed_certificate('server.example')
        leaf = verify_certificate_chain([cert_pem], [cert_pem], server_name='server.example')
        assert leaf.subject.rfc4514_string() == 'CN=server.example'

    def test_rejects_server_certificate_without_subject_alt_name(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        leaf, _leaf_key = factory.make_server_leaf('server.example', issuer_cert=root, issuer_key=root_key)
        with pytest.raises(ProtocolError, match='subjectAltName'):
            verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='server.example')

    def test_rejects_path_length_violation(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA', path_length=0)
        intermediate, intermediate_key = factory.make_ca('Intermediate CA', issuer_cert=root, issuer_key=root_key, path_length=0)
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=intermediate,
            issuer_key=intermediate_key,
            san_dns=('service.example',),
        )
        with pytest.raises(ProtocolError, match='chain verification failed'):
            verify_certificate_chain([_pem(leaf), _pem(intermediate)], [_pem(root)], server_name='service.example')

    def test_rejects_name_constraints_violation(self) -> None:
        factory = CertificateFactory()
        constraints = x509.NameConstraints(permitted_subtrees=[x509.DNSName('allowed.example')], excluded_subtrees=None)
        root, root_key = factory.make_ca('Root CA', name_constraints=constraints)
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=root,
            issuer_key=root_key,
            san_dns=('service.example',),
        )
        with pytest.raises(ProtocolError, match='chain verification failed'):
            verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example')

    def test_rejects_revoked_leaf_when_crl_is_present(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=root,
            issuer_key=root_key,
            san_dns=('service.example',),
        )
        crl = factory.make_crl(root, root_key, revoked_serials=(leaf.serial_number,))
        policy = CertificateValidationPolicy(
            revocation_mode=RevocationMode.REQUIRE,
            revocation_material=RevocationMaterial(crls=(crl,)),
        )
        with pytest.raises(ProtocolError, match='revoked'):
            verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)

    def test_requires_revocation_evidence_when_policy_requires_it(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=root,
            issuer_key=root_key,
            san_dns=('service.example',),
        )
        policy = CertificateValidationPolicy(revocation_mode=RevocationMode.REQUIRE)
        with pytest.raises(ProtocolError, match='revocation'):
            verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)

    def test_fetches_ocsp_from_aia_and_reuses_cache(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        policy = CertificateValidationPolicy(revocation_mode=RevocationMode.REQUIRE)
        assert policy.revocation_fetch_policy is not None
        with revocation_http_server({}) as server:
            leaf, _leaf_key = factory.make_server_leaf(
                'service.example',
                issuer_cert=root,
                issuer_key=root_key,
                san_dns=('service.example',),
                ocsp_uris=(server.url('/ocsp'),),
            )
            response = factory.make_ocsp_response(
                leaf,
                root,
                root_key,
                next_update=_NOW + timedelta(minutes=30),
            )
            server.responses[('POST', '/ocsp')] = _ResponseSpec(
                body=_der_ocsp(response),
                headers={
                    'Content-Type': 'application/ocsp-response',
                    'Cache-Control': 'max-age=600',
                },
            )
            verified = verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)
            assert verified.serial_number == leaf.serial_number
            assert server.count('POST', '/ocsp') == 1
        verified = verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)
        assert verified.serial_number == leaf.serial_number
        assert len(policy.revocation_fetch_policy.cache) == 1

    def test_fetches_crl_from_distribution_point(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        with revocation_http_server({}) as server:
            leaf, _leaf_key = factory.make_server_leaf(
                'service.example',
                issuer_cert=root,
                issuer_key=root_key,
                san_dns=('service.example',),
                crl_uris=(server.url('/root.crl'),),
            )
            crl = factory.make_crl(root, root_key, revoked_serials=())
            server.responses[('GET', '/root.crl')] = _ResponseSpec(
                body=_der_crl(crl),
                headers={'Content-Type': 'application/pkix-crl'},
            )
            policy = CertificateValidationPolicy(revocation_mode=RevocationMode.REQUIRE)
            verified = verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)
            assert verified.serial_number == leaf.serial_number
            assert server.count('GET', '/root.crl') == 1

    def test_soft_fail_allows_unreachable_online_revocation_source(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=root,
            issuer_key=root_key,
            san_dns=('service.example',),
            ocsp_uris=('http://127.0.0.1:9/unreachable',),
        )
        policy = CertificateValidationPolicy(
            revocation_mode=RevocationMode.SOFT_FAIL,
            revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
        )
        verified = verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)
        assert verified.serial_number == leaf.serial_number

    def test_require_mode_rejects_stale_ocsp_response(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        with revocation_http_server({}) as server:
            leaf, _leaf_key = factory.make_server_leaf(
                'service.example',
                issuer_cert=root,
                issuer_key=root_key,
                san_dns=('service.example',),
                ocsp_uris=(server.url('/stale-ocsp'),),
            )
            stale_response = factory.make_ocsp_response(
                leaf,
                root,
                root_key,
                next_update=_NOW - timedelta(hours=1),
                this_update=_NOW - timedelta(days=1),
            )
            server.responses[('POST', '/stale-ocsp')] = _ResponseSpec(
                body=_der_ocsp(stale_response),
                headers={'Content-Type': 'application/ocsp-response'},
            )
            policy = CertificateValidationPolicy(revocation_mode=RevocationMode.REQUIRE)
            with pytest.raises(ProtocolError, match='revocation status could not be established'):
                verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)

    def test_require_mode_surfaces_fetch_failure_context(self) -> None:
        factory = CertificateFactory()
        root, root_key = factory.make_ca('Root CA')
        leaf, _leaf_key = factory.make_server_leaf(
            'service.example',
            issuer_cert=root,
            issuer_key=root_key,
            san_dns=('service.example',),
            crl_uris=('http://127.0.0.1:9/missing.crl',),
        )
        policy = CertificateValidationPolicy(
            revocation_mode=RevocationMode.REQUIRE,
            revocation_fetch_policy=RevocationFetchPolicy(timeout_seconds=0.25),
        )
        with pytest.raises(ProtocolError, match='CRL http://127.0.0.1:9/missing.crl'):
            verify_certificate_chain([_pem(leaf)], [_pem(root)], server_name='service.example', policy=policy)
