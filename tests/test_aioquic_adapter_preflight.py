from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
BUNDLE_ROOT = RELEASE_ROOT / 'tigrcorn-aioquic-adapter-preflight-bundle'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _portable_path(value: str) -> str:
    return value.replace('\\', '/')


def test_aioquic_preflight_docs_bundle_and_notes_exist() -> None:
    assert (CONFORMANCE / 'AIOQUIC_ADAPTER_PREFLIGHT.md').exists()
    assert (CONFORMANCE / 'aioquic_adapter_preflight.current.json').exists()
    assert (ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md').exists()
    assert BUNDLE_ROOT.exists()
    assert (ROOT / 'tools' / 'preflight_aioquic_adapters.py').exists()

    manifest = _load_json(RELEASE_ROOT / 'manifest.json')
    assert 'aioquic_adapter_preflight' in manifest['bundles']
    assert _portable_path(manifest['bundles']['aioquic_adapter_preflight']['path']) == BUNDLE_ROOT.relative_to(ROOT).as_posix()

    bundle_index = _load_json(BUNDLE_ROOT / 'index.json')
    status = _load_json(CONFORMANCE / 'aioquic_adapter_preflight.current.json')
    assert bundle_index['artifact_root'] == status['current_state']['bundle_root']
    assert bundle_index['all_adapters_passed'] == status['current_state']['all_adapters_passed']
    assert bundle_index['all_protocols_h3'] == status['current_state']['all_protocols_h3']


def test_aioquic_preflight_bundle_preserves_two_direct_adapter_runs() -> None:
    index = _load_json(BUNDLE_ROOT / 'index.json')
    assert index['scenario_count'] == 2
    assert index['all_adapters_passed'] is True
    assert index['no_peer_exit_code_2'] is True
    assert index['negotiation_metadata_emitted'] is True
    assert index['all_protocols_h3'] is True
    assert index['all_handshakes_complete'] is True
    assert index['certificate_inputs_ready'] is True

    expected = {
        'http3-server-aioquic-client-post',
        'websocket-http3-server-aioquic-client',
    }
    assert set(index['scenario_ids']) == expected


def test_aioquic_preflight_scenario_metadata_records_certificate_and_handshake_state() -> None:
    status = _load_json(CONFORMANCE / 'aioquic_adapter_preflight.current.json')
    records = {item['scenario_id']: item for item in status['current_state']['scenario_records']}

    http3 = records['http3-server-aioquic-client-post']
    websocket = records['websocket-http3-server-aioquic-client']

    for record in (http3, websocket):
        assert record['passed'] is True
        assert record['peer_exit_code'] == 0
        assert record['protocol'] == 'h3'
        assert record['handshake_complete'] is True
        assert record['ca_cert_path'] == 'tests/fixtures_certs/interop-localhost-cert.pem'
        assert record['ca_cert_exists'] is True
        assert record['certificate_inputs_ready'] is True
        assert record['negotiation_metadata_emitted'] is True
        assert record['transcript_emitted'] is True
        assert record['packet_trace_exists'] is True
        assert record['qlog_exists'] is True

    assert http3['peer_module'] == 'tests.fixtures_third_party.aioquic_http3_client'
    assert websocket['peer_module'] == 'tests.fixtures_third_party.aioquic_http3_websocket_client'
    assert websocket['websocket_connect_protocol_enabled'] is True


def test_release_workflow_and_wrapper_require_aioquic_preflight_before_phase9_scripts() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'phase9-certification-release.yml').read_text(encoding='utf-8')
    wrapper = (ROOT / 'tools' / 'run_phase9_release_workflow.py').read_text(encoding='utf-8')
    assert 'tools/preflight_aioquic_adapters.py' in workflow
    assert '--require-pass' in workflow
    assert 'preflight_aioquic_adapters.py' in wrapper
    assert '--require-pass' in wrapper
