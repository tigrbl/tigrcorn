from __future__ import annotations

from .imports import *
from .helpers import *

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
