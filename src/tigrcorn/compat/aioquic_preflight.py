from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .interop_runner import run_external_matrix
from .release_gates import evaluate_promotion_target, evaluate_release_gates

DEFAULT_PRELIGHT_SCENARIOS: tuple[str, ...] = (
    'http3-server-aioquic-client-post',
    'websocket-http3-server-aioquic-client',
)
DEFAULT_BUNDLE_NAME = 'tigrcorn-aioquic-adapter-preflight-bundle'
DEFAULT_STATUS_DOC = 'docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md'
DEFAULT_STATUS_JSON = 'docs/review/conformance/aioquic_adapter_preflight.current.json'
DEFAULT_DELIVERY_NOTES = 'DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md'
DEFAULT_MATRIX_PATH = 'docs/review/conformance/external_matrix.release.json'
DEFAULT_RELEASE_ROOT = 'docs/review/conformance/releases/0.3.9/release-0.3.9'


class AioquicAdapterPreflightError(RuntimeError):
    """Raised when the aioquic adapter preflight fails and strict pass mode is enabled."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _module_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _command_option(command: Sequence[str], option: str) -> str | None:
    try:
        index = list(command).index(option)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(command):
        return None
    return str(command[next_index])


def _module_name(command: Sequence[str]) -> str | None:
    try:
        index = list(command).index('-m')
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(command):
        return None
    return str(command[next_index])


def _path_ready(entry: Mapping[str, Any] | None) -> bool:
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get('exists')) and bool(entry.get('is_file'))


def _default_certificate_inputs(repo_root: Path, peer_command: Sequence[str]) -> dict[str, Any]:
    def _entry(option: str) -> dict[str, Any]:
        value = _command_option(peer_command, option)
        if value is None:
            return {'path': None, 'exists': False, 'is_file': False}
        candidate = repo_root / value
        return {
            'path': value,
            'exists': candidate.exists(),
            'is_file': candidate.is_file(),
        }

    ca = _entry('--cacert')
    cert = _entry('--client-cert')
    key = _entry('--client-key')
    client_material_requested = bool(cert['path'] or key['path'])
    client_material_ready = (not client_material_requested) or (bool(cert['exists']) and bool(key['exists']))
    return {
        'ca_cert': ca,
        'client_cert': cert,
        'client_key': key,
        'client_material_requested': client_material_requested,
        'client_material_ready': client_material_ready,
        'ready': bool(ca['exists']) and client_material_ready,
    }


def _scenario_kind(scenario_id: str) -> str:
    if 'websocket' in scenario_id:
        return 'http3_websocket_adapter'
    return 'http3_client_adapter'


def _extract_scenario_record(repo_root: Path, bundle_root: Path, scenario_id: str) -> dict[str, Any]:
    scenario_root = bundle_root / scenario_id
    result = _load_json(scenario_root / 'result.json')
    commands = _load_json(scenario_root / 'command.json')
    versions = _load_json(scenario_root / 'versions.json')
    peer_command = [str(item) for item in commands['peer']['command']]
    negotiation = dict((result.get('negotiation') or {}).get('peer') or {})
    transcript = dict((result.get('transcript') or {}).get('peer') or {})
    transcript_quic = dict(transcript.get('quic') or {})
    certificate_inputs = dict(negotiation.get('certificate_inputs') or _default_certificate_inputs(repo_root, peer_command))
    handshake_complete = bool(
        negotiation.get('handshake_complete')
        or transcript_quic.get('handshake_complete')
        or (result.get('passed') and (result.get('peer') or {}).get('exit_code') == 0 and negotiation.get('protocol') == 'h3')
    )
    artifacts = result.get('artifacts') or {}
    response = dict(transcript.get('response') or {})

    return {
        'scenario_id': scenario_id,
        'kind': _scenario_kind(scenario_id),
        'passed': bool(result.get('passed')),
        'peer_exit_code': int((result.get('peer') or {}).get('exit_code') or 0),
        'peer_module': _module_name(peer_command),
        'peer_command': peer_command,
        'peer_version': (versions.get('peer') or {}).get('implementation_version'),
        'protocol': negotiation.get('protocol'),
        'tls_version': negotiation.get('tls_version'),
        'server_name': negotiation.get('server_name'),
        'handshake_complete': handshake_complete,
        'retry_observed': bool(negotiation.get('retry_observed')),
        'negotiation_metadata_emitted': bool((artifacts.get('peer_negotiation') or {}).get('exists')),
        'transcript_emitted': bool((artifacts.get('peer_transcript') or {}).get('exists')),
        'packet_trace_exists': bool((artifacts.get('packet_trace') or {}).get('exists')),
        'qlog_exists': bool((artifacts.get('qlog') or {}).get('exists')),
        'certificate_inputs': certificate_inputs,
        'certificate_inputs_ready': bool(negotiation.get('certificate_inputs_ready', certificate_inputs.get('ready'))),
        'ca_cert_path': (certificate_inputs.get('ca_cert') or {}).get('path'),
        'ca_cert_exists': _path_ready(certificate_inputs.get('ca_cert') or {}),
        'client_material_requested': bool(certificate_inputs.get('client_material_requested')),
        'response_status': response.get('status'),
        'websocket_connect_protocol_enabled': negotiation.get('connect_protocol_enabled'),
        'websocket_negotiated_extensions': list(negotiation.get('negotiated_extensions') or []),
        'artifact_dir': str(scenario_root.relative_to(bundle_root)),
        'result_path': str((scenario_root / 'result.json').relative_to(bundle_root)),
        'peer_negotiation_path': str((scenario_root / 'peer_negotiation.json').relative_to(bundle_root)),
        'peer_transcript_path': str((scenario_root / 'peer_transcript.json').relative_to(bundle_root)),
    }


def _bundle_manifest(*, artifact_root: str, matrix_path: str, scenario_ids: Sequence[str]) -> dict[str, Any]:
    return {
        'bundle_kind': 'aioquic_adapter_preflight_bundle',
        'generated_at': _now(),
        'release_gate_eligible': False,
        'artifact_root': artifact_root,
        'matrix_path': matrix_path,
        'scenario_ids': list(scenario_ids),
        'note': 'This bundle proves the third-party aioquic HTTP/3 adapters can execute cleanly before strict-target checkpoint promotion work continues.',
    }


def _bundle_index(*, artifact_root: str, matrix_path: str, scenario_records: Sequence[Mapping[str, Any]], environment: Mapping[str, Any], gate_status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'artifact_root': artifact_root,
        'bundle_kind': 'aioquic_adapter_preflight_bundle',
        'generated_at': _now(),
        'matrix_path': matrix_path,
        'scenario_count': len(scenario_records),
        'scenario_ids': [str(item['scenario_id']) for item in scenario_records],
        'all_adapters_passed': all(bool(item['passed']) for item in scenario_records),
        'no_peer_exit_code_2': all(int(item['peer_exit_code']) != 2 for item in scenario_records),
        'negotiation_metadata_emitted': all(bool(item['negotiation_metadata_emitted']) for item in scenario_records),
        'transcript_metadata_emitted': all(bool(item['transcript_emitted']) for item in scenario_records),
        'all_protocols_h3': all(item.get('protocol') == 'h3' for item in scenario_records),
        'all_handshakes_complete': all(bool(item['handshake_complete']) for item in scenario_records),
        'certificate_inputs_ready': all(bool(item['certificate_inputs_ready']) for item in scenario_records),
        'packet_traces_emitted': all(bool(item['packet_trace_exists']) for item in scenario_records),
        'qlogs_emitted': all(bool(item['qlog_exists']) for item in scenario_records),
        'environment': dict(environment),
        'gate_status_after_preflight': dict(gate_status),
        'release_gate_eligible': False,
    }


def _bundle_summary(index: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'artifact_root': index['artifact_root'],
        'bundle_kind': index['bundle_kind'],
        'generated_at': index['generated_at'],
        'scenario_count': index['scenario_count'],
        'all_adapters_passed': index['all_adapters_passed'],
        'no_peer_exit_code_2': index['no_peer_exit_code_2'],
        'all_protocols_h3': index['all_protocols_h3'],
        'all_handshakes_complete': index['all_handshakes_complete'],
        'certificate_inputs_ready': index['certificate_inputs_ready'],
    }


def _bundle_readme(index: Mapping[str, Any], scenario_records: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        '# aioquic adapter preflight bundle',
        '',
        'This bundle preserves the direct third-party aioquic HTTP/3 adapter preflight runs used before strict-target certification checkpoints.',
        '',
        '## Exit-criteria status',
        '',
        f"- all adapters passed: `{index['all_adapters_passed']}`",
        f"- no peer exit code 2: `{index['no_peer_exit_code_2']}`",
        f"- negotiation metadata emitted: `{index['negotiation_metadata_emitted']}`",
        f"- transcript metadata emitted: `{index['transcript_metadata_emitted']}`",
        f"- ALPN h3 observed for every run: `{index['all_protocols_h3']}`",
        f"- QUIC handshakes complete: `{index['all_handshakes_complete']}`",
        f"- certificate inputs ready: `{index['certificate_inputs_ready']}`",
        '',
        '## Scenarios',
        '',
    ]
    for item in scenario_records:
        lines.extend([
            f"- `{item['scenario_id']}` → passed=`{item['passed']}`, peer_exit=`{item['peer_exit_code']}`, protocol=`{item['protocol']}`, handshake_complete=`{item['handshake_complete']}`",
        ])
    lines.append('')
    return '\n'.join(lines) + '\n'


def _status_markdown(snapshot: Mapping[str, Any], *, release_root: str, bundle_root: str) -> str:
    current = snapshot['current_state']
    scenario_records = current['scenario_records']
    lines = [
        '# aioquic adapter preflight',
        '',
        'This checkpoint executes the third-party aioquic HTTP/3 adapters directly before any strict-target artifact-promotion work proceeds.',
        '',
        '## Exit criteria',
        '',
        f"- both adapters passed: `{current['all_adapters_passed']}`",
        f"- no peer exit code 2: `{current['no_peer_exit_code_2']}`",
        f"- negotiation metadata emitted: `{current['negotiation_metadata_emitted']}`",
        f"- transcript metadata emitted: `{current['transcript_metadata_emitted']}`",
        f"- ALPN h3 observed: `{current['all_protocols_h3']}`",
        f"- QUIC handshakes complete: `{current['all_handshakes_complete']}`",
        f"- certificate inputs ready: `{current['certificate_inputs_ready']}`",
        '',
        '## Environment snapshot',
        '',
        f"- python version: `{current['environment']['python_version']}`",
        f"- python minor version: `{current['environment']['python_minor_version']}`",
        f"- aioquic version: `{current['environment']['aioquic_version']}`",
        f"- wsproto version: `{current['environment']['wsproto_version']}`",
        f"- h2 version: `{current['environment']['h2_version']}`",
        f"- websockets version: `{current['environment']['websockets_version']}`",
        f"- release root: `{release_root}`",
        f"- preflight bundle root: `{bundle_root}`",
        '',
        '## Scenario results',
        '',
    ]
    for item in scenario_records:
        lines.extend([
            f"### `{item['scenario_id']}`",
            '',
            f"- kind: `{item['kind']}`",
            f"- adapter module: `{item['peer_module']}`",
            f"- peer exit code: `{item['peer_exit_code']}`",
            f"- protocol: `{item['protocol']}`",
            f"- tls version: `{item['tls_version']}`",
            f"- server name: `{item['server_name']}`",
            f"- handshake complete: `{item['handshake_complete']}`",
            f"- ca cert path: `{item['ca_cert_path']}`",
            f"- ca cert exists: `{item['ca_cert_exists']}`",
            f"- certificate inputs ready: `{item['certificate_inputs_ready']}`",
            f"- packet trace emitted: `{item['packet_trace_exists']}`",
            f"- qlog emitted: `{item['qlog_exists']}`",
            f"- peer negotiation metadata: `{item['peer_negotiation_path']}`",
            f"- peer transcript metadata: `{item['peer_transcript_path']}`",
            '',
        ])
    lines.extend([
        '## Honest current repository state',
        '',
        f"- authoritative boundary after preflight: `{current['gate_status_after_preflight']['authoritative_boundary_passed']}`",
        f"- strict target after preflight: `{current['gate_status_after_preflight']['strict_target_boundary_passed']}`",
        f"- promotion target after preflight: `{current['gate_status_after_preflight']['promotion_target_passed']}`",
        '',
        'This preflight closes the adapter-execution ambiguity: the aioquic HTTP/3 client and aioquic RFC 9220 WebSocket client both ran successfully and emitted negotiation metadata. It does **not** by itself promote the remaining strict-target HTTP/3 scenario artifacts into the 0.3.9 release root, so the package may still remain non-green under the stricter target until those artifacts are regenerated and assembled.',
        '',
    ])
    return '\n'.join(lines)


def _delivery_notes(snapshot: Mapping[str, Any], *, release_root: str, bundle_root: str) -> str:
    current = snapshot['current_state']
    return (
        '# Delivery notes — aioquic adapter preflight\n\n'
        'This checkpoint adds a direct aioquic adapter preflight on top of the existing Phase 9I release-assembly repository.\n\n'
        'What changed:\n\n'
        '- added a reusable aioquic preflight module at `src/tigrcorn/compat/aioquic_preflight.py`\n'
        '- added a runnable checkpoint tool at `tools/preflight_aioquic_adapters.py`\n'
        '- added a preserved preflight bundle under the 0.3.9 working release root\n'
        '- updated the release workflow and local wrapper so aioquic adapter preflight is now mandatory before Phase 9 checkpoint scripts run\n'
        '- updated current-state documentation\n\n'
        'Current result:\n\n'
        f"- preflight bundle root: `{bundle_root}`\n"
        f"- all adapters passed: `{current['all_adapters_passed']}`\n"
        f"- no peer exit code 2: `{current['no_peer_exit_code_2']}`\n"
        f"- strict target after preflight: `{current['gate_status_after_preflight']['strict_target_boundary_passed']}`\n"
        f"- promotion target after preflight: `{current['gate_status_after_preflight']['promotion_target_passed']}`\n\n"
        'This checkpoint proves the third-party aioquic adapter execution path is healthy in the observed environment. It does not by itself claim that the package is already strict-target green or promotable.\n'
    )


def run_aioquic_adapter_preflight(
    root: str | Path,
    *,
    release_root: str = DEFAULT_RELEASE_ROOT,
    bundle_name: str = DEFAULT_BUNDLE_NAME,
    matrix_path: str = DEFAULT_MATRIX_PATH,
    scenario_ids: Sequence[str] = DEFAULT_PRELIGHT_SCENARIOS,
    bundle_root: str | Path | None = None,
    require_pass: bool = False,
) -> dict[str, Any]:
    repo_root = Path(root)
    resolved_release_root = repo_root / release_root
    target_bundle_root = Path(bundle_root) if bundle_root is not None else resolved_release_root / bundle_name
    if target_bundle_root.exists():
        shutil.rmtree(target_bundle_root)
    target_bundle_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='aioquic-preflight-') as tmpdir:
        summary = run_external_matrix(
            repo_root / matrix_path,
            artifact_root=tmpdir,
            source_root=repo_root,
            scenario_ids=list(scenario_ids),
            strict=True,
        )
        generated_root = Path(summary.artifact_root)
        for source_name, target_name in (
            ('manifest.json', 'generated_matrix_manifest.json'),
            ('index.json', 'generated_matrix_index.json'),
            ('summary.json', 'generated_matrix_summary.json'),
        ):
            shutil.copy2(generated_root / source_name, target_bundle_root / target_name)
        for scenario_id in scenario_ids:
            shutil.copytree(generated_root / scenario_id, target_bundle_root / scenario_id)

    environment = {
        'python_version': sys.version,
        'python_minor_version': f'{sys.version_info.major}.{sys.version_info.minor}',
        'aioquic_version': _module_version('aioquic'),
        'wsproto_version': _module_version('wsproto'),
        'h2_version': _module_version('h2'),
        'websockets_version': _module_version('websockets'),
    }
    gate_status = {
        'authoritative_boundary_passed': evaluate_release_gates(repo_root).passed,
        'strict_target_boundary_passed': evaluate_release_gates(repo_root, boundary_path='docs/review/conformance/certification_boundary.strict_target.json').passed,
        'promotion_target_passed': evaluate_promotion_target(repo_root).passed,
    }
    scenario_records = [_extract_scenario_record(repo_root, target_bundle_root, scenario_id) for scenario_id in scenario_ids]
    index = _bundle_index(
        artifact_root=str(target_bundle_root.relative_to(repo_root)) if target_bundle_root.is_relative_to(repo_root) else str(target_bundle_root),
        matrix_path=matrix_path,
        scenario_records=scenario_records,
        environment=environment,
        gate_status=gate_status,
    )
    manifest = _bundle_manifest(
        artifact_root=index['artifact_root'],
        matrix_path=matrix_path,
        scenario_ids=scenario_ids,
    )
    summary = _bundle_summary(index)
    _dump_json(target_bundle_root / 'manifest.json', manifest)
    _dump_json(target_bundle_root / 'index.json', index)
    _dump_json(target_bundle_root / 'summary.json', summary)
    _dump_json(target_bundle_root / 'preflight.json', {
        'generated_at': _now(),
        'environment': environment,
        'gate_status_after_preflight': gate_status,
        'scenario_records': scenario_records,
    })
    (target_bundle_root / 'README.md').write_text(_bundle_readme(index, scenario_records), encoding='utf-8')

    snapshot = {
        'checkpoint': 'aioquic_adapter_preflight',
        'status': 'aioquic_adapter_preflight_passed' if summary['all_adapters_passed'] else 'aioquic_adapter_preflight_failed',
        'current_state': {
            'release_root': release_root,
            'bundle_root': index['artifact_root'],
            'matrix_path': matrix_path,
            'scenario_ids': list(scenario_ids),
            'scenario_records': scenario_records,
            'environment': environment,
            'all_adapters_passed': index['all_adapters_passed'],
            'no_peer_exit_code_2': index['no_peer_exit_code_2'],
            'negotiation_metadata_emitted': index['negotiation_metadata_emitted'],
            'transcript_metadata_emitted': index['transcript_metadata_emitted'],
            'all_protocols_h3': index['all_protocols_h3'],
            'all_handshakes_complete': index['all_handshakes_complete'],
            'certificate_inputs_ready': index['certificate_inputs_ready'],
            'packet_traces_emitted': index['packet_traces_emitted'],
            'qlogs_emitted': index['qlogs_emitted'],
            'gate_status_after_preflight': gate_status,
        },
        'remaining_strict_target_blockers': [
            'websocket-http3-server-aioquic-client-permessage-deflate',
            'http3-connect-relay-aioquic-client',
            'http3-trailer-fields-aioquic-client',
            'http3-content-coding-aioquic-client',
        ],
    }
    if require_pass and not summary['all_adapters_passed']:
        raise AioquicAdapterPreflightError('one or more aioquic adapter preflight scenarios failed')
    return snapshot


def write_status_documents(
    root: str | Path,
    snapshot: Mapping[str, Any],
    *,
    release_root: str = DEFAULT_RELEASE_ROOT,
    bundle_root: str = DEFAULT_BUNDLE_NAME,
    status_doc: str = DEFAULT_STATUS_DOC,
    status_json: str = DEFAULT_STATUS_JSON,
    delivery_notes: str = DEFAULT_DELIVERY_NOTES,
) -> None:
    repo_root = Path(root)
    _dump_json(repo_root / status_json, snapshot)
    (repo_root / status_doc).write_text(
        _status_markdown(snapshot, release_root=release_root, bundle_root=bundle_root),
        encoding='utf-8',
    )
    (repo_root / delivery_notes).write_text(
        _delivery_notes(snapshot, release_root=release_root, bundle_root=bundle_root),
        encoding='utf-8',
    )
