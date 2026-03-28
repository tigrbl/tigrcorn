from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.interop_runner import run_external_matrix  # noqa: E402
from tigrcorn.compat.release_gates import validate_independent_certification_bundle  # noqa: E402
from tigrcorn.errors import ProtocolError  # noqa: E402
from tigrcorn.security.x509.path import (  # noqa: E402
    CertificatePurpose,
    CertificateValidationPolicy,
    RevocationFetchPolicy,
    RevocationMode,
    verify_certificate_chain,
)
from tests.fixtures_pkg.interop_ocsp_fixtures import (  # noqa: E402
    CertificateFactory,
    ResponseSpec,
    der_ocsp,
    pem_certificate,
    pem_private_key,
    revocation_http_server,
    write_bytes,
    write_pem_chain,
)
from tools.interop_wrappers import describe_wrapper_registry, write_wrapper_registry_json  # noqa: E402
from tools.retrofit_independent_bundle_schema import retrofit_bundle  # noqa: E402

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
INDEPENDENT_ROOT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
LOCAL_VALIDATION_ROOT = RELEASE_ROOT / 'tigrcorn-ocsp-local-validation-artifacts'
MATRIX_PATH = CONFORMANCE / 'external_matrix.release.json'
WRAPPER_JSON = CONFORMANCE / 'interop_wrapper_registry.current.json'
TMP_ROOT = ROOT / '.artifacts' / 'phase9e_ocsp_runs'
SCENARIO_ID = 'tls-server-ocsp-validation-openssl-client'
COMMIT_HASH = 'phase9e-ocsp-checkpoint'


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=_json_default) + '\n', encoding='utf-8')


def _replace_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_replace_paths(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace_paths(item, old, new) for key, item in value.items()}
    return value


def _rewrite_json_tree(root: Path, old: str, new: str) -> None:
    for path in root.rglob('*.json'):
        payload = _load_json(path)
        payload = _replace_paths(payload, old, new)
        _write_json(path, payload)


def _scenario_entries(index_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry['id']): entry for entry in index_payload.get('scenarios', []) if entry.get('id') is not None}


def _build_ocsp_materials(base_dir: Path, responder) -> dict[str, Any]:
    base_dir.mkdir(parents=True, exist_ok=True)
    factory = CertificateFactory()
    root, root_key = factory.make_ca('Root CA', path_length=1)
    issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
    server_leaf, server_key = factory.make_server_leaf(
        'localhost',
        issuer_cert=issuer,
        issuer_key=issuer_key,
        san_dns=('localhost',),
        san_ips=('127.0.0.1',),
    )
    client_good, client_good_key = factory.make_client_leaf(
        'client.good.local',
        issuer_cert=issuer,
        issuer_key=issuer_key,
        ocsp_uris=(responder.url('/ocsp-good'),),
    )
    client_revoked, client_revoked_key = factory.make_client_leaf(
        'client.revoked.local',
        issuer_cert=issuer,
        issuer_key=issuer_key,
        ocsp_uris=(responder.url('/ocsp-revoked'),),
    )
    client_stale, client_stale_key = factory.make_client_leaf(
        'client.stale.local',
        issuer_cert=issuer,
        issuer_key=issuer_key,
        ocsp_uris=(responder.url('/ocsp-stale'),),
    )
    now = datetime.now(timezone.utc)
    responder.responses[('POST', '/ocsp-good')] = ResponseSpec(
        body=der_ocsp(factory.make_ocsp_response(client_good, issuer, issuer_key, next_update=now + timedelta(minutes=30))),
        headers={'Content-Type': 'application/ocsp-response', 'Cache-Control': 'max-age=600'},
    )
    responder.responses[('POST', '/ocsp-revoked')] = ResponseSpec(
        body=der_ocsp(factory.make_ocsp_response(client_revoked, issuer, issuer_key, cert_status=__import__('cryptography.x509').x509.ocsp.OCSPCertStatus.REVOKED, next_update=now + timedelta(minutes=30))),
        headers={'Content-Type': 'application/ocsp-response'},
    )
    responder.responses[('POST', '/ocsp-stale')] = ResponseSpec(
        body=der_ocsp(factory.make_ocsp_response(client_stale, issuer, issuer_key, next_update=now - timedelta(hours=1), this_update=now - timedelta(days=1))),
        headers={'Content-Type': 'application/ocsp-response'},
    )

    paths = {
        'ca_bundle': write_pem_chain(base_dir / 'ca_bundle.pem', [root, issuer]),
        'server_chain': write_pem_chain(base_dir / 'server_chain.pem', [server_leaf, issuer]),
        'server_key': write_bytes(base_dir / 'server_key.pem', pem_private_key(server_key)),
        'client_good_chain': write_pem_chain(base_dir / 'client_good_chain.pem', [client_good, issuer]),
        'client_good_key': write_bytes(base_dir / 'client_good_key.pem', pem_private_key(client_good_key)),
        'client_revoked_chain': write_pem_chain(base_dir / 'client_revoked_chain.pem', [client_revoked, issuer]),
        'client_revoked_key': write_bytes(base_dir / 'client_revoked_key.pem', pem_private_key(client_revoked_key)),
        'client_stale_chain': write_pem_chain(base_dir / 'client_stale_chain.pem', [client_stale, issuer]),
        'client_stale_key': write_bytes(base_dir / 'client_stale_key.pem', pem_private_key(client_stale_key)),
    }
    metadata = {
        'generated_at': _now(),
        'paths': {key: str(value) for key, value in paths.items()},
        'ocsp_urls': {
            'good': responder.url('/ocsp-good'),
            'revoked': responder.url('/ocsp-revoked'),
            'stale': responder.url('/ocsp-stale'),
            'unreachable': 'http://127.0.0.1:9/unreachable',
        },
        'serials': {
            'server': server_leaf.serial_number,
            'client_good': client_good.serial_number,
            'client_revoked': client_revoked.serial_number,
            'client_stale': client_stale.serial_number,
        },
    }
    _write_json(base_dir / 'materials.json', metadata)
    return {
        'factory': factory,
        'root': root,
        'issuer': issuer,
        'paths': paths,
        'metadata': metadata,
    }


def _patched_matrix_for_ocsp(materials: dict[str, Any], tmp_root: Path) -> Path:
    payload = _load_json(MATRIX_PATH)
    scenarios = [scenario for scenario in payload.get('scenarios', []) if scenario.get('id') == SCENARIO_ID]
    if not scenarios:
        raise KeyError(f'missing scenario row: {SCENARIO_ID}')
    scenario = json.loads(json.dumps(scenarios[0]))
    scenario['sut']['env']['INTEROP_OCSP_CERTFILE'] = str(materials['paths']['server_chain'])
    scenario['sut']['env']['INTEROP_OCSP_KEYFILE'] = str(materials['paths']['server_key'])
    scenario['sut']['env']['INTEROP_OCSP_CA_CERTS'] = str(materials['paths']['ca_bundle'])
    scenario['peer_process']['env']['INTEROP_CAFILE'] = str(materials['paths']['ca_bundle'])
    scenario['peer_process']['env']['INTEROP_CLIENT_CERT'] = str(materials['paths']['client_good_chain'])
    scenario['peer_process']['env']['INTEROP_CLIENT_KEY'] = str(materials['paths']['client_good_key'])
    matrix = {
        'metadata': {
            'bundle_kind': 'independent_certification',
            'phase9b_wrapper_families': describe_wrapper_registry()['families'],
        },
        'name': 'phase9e-ocsp-proof',
        'scenarios': [scenario],
    }
    path = tmp_root / 'matrix.json'
    _write_json(path, matrix)
    return path


def _overlay_generated_scenario(generated_root: Path, responder) -> None:
    retrofit_bundle(INDEPENDENT_ROOT)
    index_path = INDEPENDENT_ROOT / 'index.json'
    summary_path = INDEPENDENT_ROOT / 'summary.json'
    manifest_path = INDEPENDENT_ROOT / 'manifest.json'
    index_payload = _load_json(index_path)
    summary_payload = _load_json(summary_path)
    manifest_payload = _load_json(manifest_path)
    entries = _scenario_entries(index_payload)

    source_root_str = str(generated_root)
    destination_root_str = str(INDEPENDENT_ROOT.relative_to(ROOT))
    src_dir = generated_root / SCENARIO_ID
    dst_dir = INDEPENDENT_ROOT / SCENARIO_ID
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    _rewrite_json_tree(dst_dir, source_root_str, destination_root_str)
    result_path = dst_dir / 'result.json'
    result_payload = _load_json(result_path)
    result_payload['ocsp_responder'] = {
        'good_request_count': responder.count('POST', '/ocsp-good'),
        'request_log': [
            {
                'method': method,
                'path': path,
                'body_length': len(body),
                'headers': headers,
            }
            for method, path, body, headers in responder.requests
        ],
    }
    _write_json(result_path, result_payload)

    entries[SCENARIO_ID] = {
        'artifact_dir': str(dst_dir.relative_to(ROOT)),
        'assertions_failed': list(result_payload.get('assertions_failed', [])),
        'error': result_payload.get('error'),
        'id': SCENARIO_ID,
        'index_path': str((dst_dir / 'index.json').relative_to(ROOT)),
        'passed': bool(result_payload.get('passed', False)),
        'result_path': str(result_path.relative_to(ROOT)),
        'summary_path': str((dst_dir / 'summary.json').relative_to(ROOT)),
        'source_bundle': str(generated_root.relative_to(ROOT)),
    }

    scenarios = [entries[key] for key in sorted(entries)]
    passed = sum(1 for entry in scenarios if entry.get('passed'))
    failed = sum(1 for entry in scenarios if not entry.get('passed'))
    wrapper_families = describe_wrapper_registry()['families']
    index_payload.update({
        'artifact_root': str(INDEPENDENT_ROOT.relative_to(ROOT)),
        'bundle_kind': 'independent_certification',
        'commit_hash': COMMIT_HASH,
        'total': len(scenarios),
        'passed': passed,
        'failed': failed,
        'scenarios': scenarios,
        'wrapper_families': wrapper_families,
    })
    summary_payload.update({
        'artifact_root': str(INDEPENDENT_ROOT.relative_to(ROOT)),
        'bundle_kind': 'independent_certification',
        'commit_hash': COMMIT_HASH,
        'scenario_ids': [item['id'] for item in scenarios],
        'total': len(scenarios),
        'passed': passed,
        'failed': failed,
        'wrapper_families': wrapper_families,
    })
    feature_values = set(manifest_payload.get('dimensions', {}).get('feature', []))
    feature_values.add('ocsp-revocation-validation')
    manifest_payload['dimensions']['feature'] = sorted(feature_values)
    manifest_payload['artifact_schema_version'] = 1
    manifest_payload['commit_hash'] = COMMIT_HASH
    manifest_payload['generated_at'] = _now()
    manifest_payload['required_bundle_files'] = ['manifest.json', 'summary.json', 'index.json']
    manifest_payload['required_scenario_files'] = ['summary.json', 'index.json', 'result.json', 'scenario.json', 'command.json', 'env.json', 'versions.json', 'wire_capture.json']
    manifest_payload['wrapper_families'] = wrapper_families
    notes = list(manifest_payload.get('notes', []))
    note = 'Phase 9E overlays a fresh OpenSSL OCSP/mTLS independent-artifact run into the 0.3.9 working release root.'
    if note not in notes:
        notes.append(note)
    manifest_payload['notes'] = notes
    _write_json(index_path, index_payload)
    _write_json(summary_path, summary_payload)
    _write_json(manifest_path, manifest_payload)


def _local_validation_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    factory = CertificateFactory()
    with revocation_http_server({}) as server:
        root, root_key = factory.make_ca('Root CA', path_length=1)
        issuer, issuer_key = factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
        good_leaf, _ = factory.make_client_leaf('client.good.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-good'),))
        revoked_leaf, _ = factory.make_client_leaf('client.revoked.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-revoked'),))
        stale_leaf, _ = factory.make_client_leaf('client.stale.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=(server.url('/ocsp-stale'),))
        server.responses[('POST', '/ocsp-good')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(good_leaf, issuer, issuer_key, next_update=datetime.now(timezone.utc) + timedelta(minutes=30))),
            headers={'Content-Type': 'application/ocsp-response', 'Cache-Control': 'max-age=600'},
        )
        server.responses[('POST', '/ocsp-revoked')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(revoked_leaf, issuer, issuer_key, cert_status=__import__('cryptography.x509').x509.ocsp.OCSPCertStatus.REVOKED, next_update=datetime.now(timezone.utc) + timedelta(minutes=30))),
            headers={'Content-Type': 'application/ocsp-response'},
        )
        server.responses[('POST', '/ocsp-stale')] = ResponseSpec(
            body=der_ocsp(factory.make_ocsp_response(stale_leaf, issuer, issuer_key, next_update=datetime.now(timezone.utc) - timedelta(hours=1), this_update=datetime.now(timezone.utc) - timedelta(days=1))),
            headers={'Content-Type': 'application/ocsp-response'},
        )
        trust = [pem_certificate(root), pem_certificate(issuer)]
        # cache reuse / good response
        policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        verify_certificate_chain([pem_certificate(good_leaf), pem_certificate(issuer)], trust, policy=policy)
        verify_certificate_chain([pem_certificate(good_leaf), pem_certificate(issuer)], trust, policy=policy)
        vectors.append({
            'id': 'ocsp-good-response-cache-reuse-client-auth',
            'passed': server.count('POST', '/ocsp-good') == 1,
            'result': {
                'request_count': server.count('POST', '/ocsp-good'),
                'expected_request_count': 1,
            },
            'source_tests': ['tests/test_phase9e_ocsp_local_validation.py::test_good_ocsp_response_is_cached_for_client_auth'],
        })

        # stale response require failure
        stale_policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        stale_error = None
        try:
            verify_certificate_chain([pem_certificate(stale_leaf), pem_certificate(issuer)], trust, policy=stale_policy)
        except ProtocolError as exc:
            stale_error = str(exc)
        vectors.append({
            'id': 'ocsp-stale-response-require-fails',
            'passed': stale_error is not None and 'revocation status could not be established' in stale_error,
            'result': {'error': stale_error},
            'source_tests': ['tests/test_phase9e_ocsp_local_validation.py::test_stale_ocsp_response_fails_in_require_mode'],
        })

        # revoked client cert require failure
        revoked_policy = CertificateValidationPolicy(purpose=CertificatePurpose.CLIENT_AUTH, revocation_mode=RevocationMode.REQUIRE)
        revoked_error = None
        try:
            verify_certificate_chain([pem_certificate(revoked_leaf), pem_certificate(issuer)], trust, policy=revoked_policy)
        except ProtocolError as exc:
            revoked_error = str(exc)
        vectors.append({
            'id': 'ocsp-revoked-client-certificate-fails',
            'passed': revoked_error is not None and 'revoked' in revoked_error,
            'result': {'error': revoked_error},
            'source_tests': ['tests/test_phase9e_ocsp_local_validation.py::test_revoked_client_certificate_fails_in_require_mode'],
        })

    unavailable_factory = CertificateFactory()
    root, root_key = unavailable_factory.make_ca('Root CA', path_length=1)
    issuer, issuer_key = unavailable_factory.make_ca('Issuer CA', issuer_cert=root, issuer_key=root_key, path_length=0)
    unreachable_leaf, _ = unavailable_factory.make_client_leaf('client.unreachable.local', issuer_cert=issuer, issuer_key=issuer_key, ocsp_uris=('http://127.0.0.1:9/unreachable',))
    trust = [pem_certificate(root), pem_certificate(issuer)]
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
    soft_ok = False
    require_error = None
    try:
        verify_certificate_chain([pem_certificate(unreachable_leaf), pem_certificate(issuer)], trust, policy=soft_policy)
        soft_ok = True
    except ProtocolError:
        soft_ok = False
    try:
        verify_certificate_chain([pem_certificate(unreachable_leaf), pem_certificate(issuer)], trust, policy=require_policy)
    except ProtocolError as exc:
        require_error = str(exc)
    vectors.append({
        'id': 'ocsp-unreachable-soft-fail-vs-require',
        'passed': soft_ok and require_error is not None and 'OCSP http://127.0.0.1:9/unreachable' in require_error,
        'result': {'soft_fail_passed': soft_ok, 'require_error': require_error},
        'source_tests': ['tests/test_phase9e_ocsp_local_validation.py::test_unreachable_responder_soft_fail_and_require_modes_diverge'],
    })
    return vectors


def _create_local_validation_bundle() -> None:
    if LOCAL_VALIDATION_ROOT.exists():
        shutil.rmtree(LOCAL_VALIDATION_ROOT)
    LOCAL_VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    vectors = _local_validation_vectors()
    scenarios = []
    for vector in vectors:
        scenario_dir = LOCAL_VALIDATION_ROOT / vector['id']
        scenario_dir.mkdir(parents=True, exist_ok=True)
        _write_json(scenario_dir / 'result.json', vector)
        scenarios.append({'id': vector['id'], 'passed': bool(vector['passed']), 'artifact_dir': str(scenario_dir.relative_to(ROOT))})
    _write_json(LOCAL_VALIDATION_ROOT / 'manifest.json', {
        'bundle_kind': 'local_validation_artifacts',
        'phase': '9E',
        'rfc': ['RFC 6960'],
        'generated_at': _now(),
        'commit_hash': COMMIT_HASH,
        'description': 'Local OCSP validation vectors preserved during Phase 9E independent OCSP closure work.',
    })
    _write_json(LOCAL_VALIDATION_ROOT / 'index.json', {
        'artifact_root': str(LOCAL_VALIDATION_ROOT.relative_to(ROOT)),
        'bundle_kind': 'local_validation_artifacts',
        'total': len(scenarios),
        'passed': sum(1 for s in scenarios if s['passed']),
        'failed': sum(1 for s in scenarios if not s['passed']),
        'scenarios': scenarios,
    })
    _write_json(LOCAL_VALIDATION_ROOT / 'summary.json', {
        'artifact_root': str(LOCAL_VALIDATION_ROOT.relative_to(ROOT)),
        'bundle_kind': 'local_validation_artifacts',
        'total': len(scenarios),
        'passed': sum(1 for s in scenarios if s['passed']),
        'failed': sum(1 for s in scenarios if not s['passed']),
        'scenario_ids': [s['id'] for s in scenarios],
    })


def _update_release_root_manifest() -> None:
    manifest_path = RELEASE_ROOT / 'manifest.json'
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    manifest.update({
        'release': '0.3.9',
        'schema_version': 1,
        'generated_at': _now(),
        'source_checkpoint': 'phase9e_ocsp',
        'status': 'phase9e_ocsp_independent_green_remaining_http3_blockers',
        'promotion_ready': False,
        'strict_target_complete': False,
    })
    bundles = dict(manifest.get('bundles', {}))
    bundles['independent_certification'] = {
        'path': str(INDEPENDENT_ROOT.relative_to(ROOT)),
        'scenario_count': len(_load_json(INDEPENDENT_ROOT / 'index.json').get('scenarios', [])),
        'release_gate_eligible': True,
        'ocsp_validation_scenario': SCENARIO_ID,
    }
    bundles['local_ocsp_validation_artifacts'] = {
        'path': str(LOCAL_VALIDATION_ROOT.relative_to(ROOT)),
        'release_gate_eligible': False,
        'vector_count': len(_load_json(LOCAL_VALIDATION_ROOT / 'index.json').get('scenarios', [])),
    }
    manifest['bundles'] = bundles
    notes = list(manifest.get('notes', []))
    add_notes = [
        'Phase 9E overlays a passing OpenSSL OCSP validation scenario into the 0.3.9 working release root.',
        'Phase 9E also preserves local OCSP validation vectors for stale responses, revoked client certificates, soft-fail vs require behavior, and cache reuse.',
        'This release root remains non-promotable because the remaining HTTP/3 strict-target blockers, flag gaps, and strict performance target are still incomplete.',
    ]
    for note in add_notes:
        if note not in notes:
            notes.append(note)
    manifest['notes'] = notes
    _write_json(manifest_path, manifest)

    readme = RELEASE_ROOT / 'README.md'
    readme.write_text(
        '# Release 0.3.9 working promotion root\n\n'
        'This directory remains the next promotable release root reserved by Phase 9A.\n\n'
        'Phase 9B adds the shared independent-certification harness foundation proof bundle.\n'
        'Phase 9C adds an RFC 7692 independent-artifact overlay into the canonical independent bundle for this working root.\n'
        'Phase 9D1 adds a CONNECT relay independent-artifact overlay into the canonical independent bundle for this working root.\n'
        'Phase 9D2 adds a trailer-fields independent-artifact overlay into the canonical independent bundle for this working root.\n'
        'Phase 9D3 adds a content-coding independent-artifact overlay into the canonical independent bundle for this working root.\n'
        'Phase 9E adds an OpenSSL OCSP validation independent-artifact overlay into the canonical independent bundle for this working root.\n\n'
        'Current truth:\n\n'
        '- the release root is **not** yet promotable\n'
        '- the OpenSSL OCSP validation scenario now passes under the 0.3.9 working release root\n'
        '- the remaining strict-target blockers are now concentrated in the HTTP/3 third-party scenarios for RFC 7692, CONNECT relay, trailer fields, and content coding\n'
        '- the strict target is therefore **not** yet complete\n',
        encoding='utf-8',
    )


def main() -> None:
    write_wrapper_registry_json(WRAPPER_JSON)
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
        tmp_root = Path(td)
        with revocation_http_server({}) as responder:
            materials = _build_ocsp_materials(tmp_root / 'materials', responder)
            matrix_path = _patched_matrix_for_ocsp(materials, tmp_root)
            summary = run_external_matrix(
                matrix_path,
                artifact_root=tmp_root / 'run',
                source_root=ROOT,
                scenario_ids=[SCENARIO_ID],
            )
            generated_bundle = Path(summary.artifact_root)
            _overlay_generated_scenario(generated_bundle, responder)
    _create_local_validation_bundle()
    _update_release_root_manifest()
    report = validate_independent_certification_bundle(INDEPENDENT_ROOT, required_scenarios=[SCENARIO_ID])
    if not report.passed:
        raise SystemExit('independent bundle validation failed after Phase 9E overlay')


if __name__ == '__main__':
    main()
