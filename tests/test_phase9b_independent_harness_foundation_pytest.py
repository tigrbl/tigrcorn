from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix
from tigrcorn.compat.release_gates import validate_independent_certification_bundle
from tools.interop_wrappers import describe_wrapper_registry


ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
BUNDLE_ROOT = RELEASE_ROOT / 'tigrcorn-independent-harness-foundation-bundle'
PYTHON = sys.executable


def _write_matrix(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / 'matrix.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_phase9b_docs_wrapper_registry_and_release_root_exist() -> None:
    doc = CONFORMANCE / 'PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md'
    schema_doc = CONFORMANCE / 'INTEROP_HARNESS_ARTIFACT_SCHEMA.md'
    status_json = CONFORMANCE / 'phase9b_independent_harness.current.json'
    wrapper_json = CONFORMANCE / 'interop_wrapper_registry.current.json'
    delivery = ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md'

    assert doc.exists()
    assert schema_doc.exists()
    assert status_json.exists()
    assert wrapper_json.exists()
    assert delivery.exists()
    assert BUNDLE_ROOT.exists()

    payload = json.loads(status_json.read_text(encoding='utf-8'))
    assert payload['phase'] == '9B'
    assert payload['status'] == 'harness_foundation_complete_not_yet_strict_complete'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is False
    assert payload['current_state']['proof_bundle_validator_passed'] is True
    assert payload['proof_bundle']['path'].endswith('tigrcorn-independent-harness-foundation-bundle')
    assert payload['proof_bundle']['proof_scenarios'] == ['http1-server-curl-client']


def test_wrapper_registry_covers_the_phase9b_peer_families() -> None:
    registry = describe_wrapper_registry()
    assert registry['module'] == 'tools.interop_wrappers'
    assert set(registry['families']) == {'curl', 'websockets', 'h2', 'aioquic', 'openssl'}
    assert registry['families']['curl'] == ['curl.http1_client', 'curl.http2_client']
    assert 'aioquic.http3_client' in registry['families']['aioquic']
    assert 'openssl.quic_client' in registry['families']['openssl']


def test_phase9b_proof_bundle_validates_and_contains_required_artifacts() -> None:
    report = validate_independent_certification_bundle(
        BUNDLE_ROOT,
        required_scenarios=['http1-server-curl-client'],
    )
    assert report.passed is True
    assert report.failures == []

    manifest = json.loads((BUNDLE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    index_payload = json.loads((BUNDLE_ROOT / 'index.json').read_text(encoding='utf-8'))
    scenario_root = BUNDLE_ROOT / 'http1-server-curl-client'

    assert manifest['bundle_kind'] == 'independent_harness_foundation'
    assert manifest['phase'] == '9B'
    assert manifest['proof_scenarios'] == ['http1-server-curl-client']
    assert index_payload['total'] == 1
    assert index_payload['passed'] == 1
    assert scenario_root.exists()
    for filename in ('summary.json', 'index.json', 'result.json', 'scenario.json', 'command.json', 'env.json', 'versions.json', 'wire_capture.json'):
        assert (scenario_root / filename).exists()


def test_bundle_validator_rejects_missing_required_scenario_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        clone_root = Path(tmpdir) / 'bundle'
        shutil.copytree(BUNDLE_ROOT, clone_root)
        (clone_root / 'http1-server-curl-client' / 'env.json').unlink()
        report = validate_independent_certification_bundle(
            clone_root,
            required_scenarios=['http1-server-curl-client'],
        )
    assert report.passed is False
    assert any('env.json' in failure for failure in report.failures)


def test_runner_emits_phase9b_artifact_schema_for_new_runs() -> None:
    payload = {
        'metadata': {
            'bundle_kind': 'independent_certification',
            'phase9b_wrapper_families': describe_wrapper_registry()['families'],
        },
        'name': 'phase9b-runner-proof',
        'scenarios': [
            {
                'id': 'http1-server-fixture-client',
                'protocol': 'http1',
                'role': 'server',
                'feature': 'post-echo',
                'peer': 'fixture-http-client',
                'sut': {
                    'name': 'tigrcorn-http1',
                    'adapter': 'subprocess',
                    'role': 'server',
                    'command': [PYTHON, '-m', 'tigrcorn', 'examples.echo_http.app:app', '--host', '{bind_host}', '--port', '{bind_port}', '--protocol', 'http1', '--disable-websocket', '--no-access-log', '--lifespan', 'off'],
                    'ready_pattern': 'listening on',
                    'version_command': [PYTHON, '-m', 'tigrcorn', '--help'],
                },
                'peer_process': {
                    'name': 'fixture-http-client',
                    'adapter': 'subprocess',
                    'role': 'client',
                    'command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client'],
                    'version_command': [PYTHON, '-m', 'tests.fixtures_pkg.interop_http_client', '--version'],
                },
                'assertions': [
                    {'path': 'peer.exit_code', 'equals': 0},
                    {'path': 'transcript.peer.response.status', 'equals': 200},
                    {'path': 'transcript.peer.response.body', 'equals': 'echo:hello-interop'},
                ],
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        matrix_path = _write_matrix(tmp_root, payload)
        prior = os.environ.get('TIGRCORN_COMMIT_HASH')
        os.environ['TIGRCORN_COMMIT_HASH'] = 'phase9b-runner-test'
        try:
            runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=tmp_root, source_root=ROOT)
            summary = runner.run()
        finally:
            if prior is None:
                os.environ.pop('TIGRCORN_COMMIT_HASH', None)
            else:
                os.environ['TIGRCORN_COMMIT_HASH'] = prior

        run_root = Path(summary.artifact_root)
        scenario_root = run_root / 'http1-server-fixture-client'
        assert (run_root / 'summary.json').exists()
        assert (run_root / 'index.json').exists()
        assert (scenario_root / 'summary.json').exists()
        assert (scenario_root / 'index.json').exists()
        assert (scenario_root / 'command.json').exists()
        assert (scenario_root / 'env.json').exists()
        assert (scenario_root / 'versions.json').exists()
        assert (scenario_root / 'wire_capture.json').exists()

        scenario_index = json.loads((scenario_root / 'index.json').read_text(encoding='utf-8'))
        assert scenario_index['artifact_files']['env.json']['exists'] is True
        assert scenario_index['artifact_files']['command.json']['exists'] is True
        assert scenario_index['artifact_files']['versions.json']['exists'] is True
        assert scenario_index['artifact_files']['wire_capture.json']['exists'] is True
