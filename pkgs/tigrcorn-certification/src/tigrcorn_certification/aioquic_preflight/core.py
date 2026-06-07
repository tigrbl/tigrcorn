from __future__ import annotations

from .imports import *
from .helpers import *
from .records import *
from .bundle import *
from .status_docs import *

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
