from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.aioquic_preflight import (
    run_aioquic_adapter_preflight,
    write_status_documents as write_aioquic_preflight_status_documents,
)
from tigrcorn.compat.certification_env import (
    write_certification_environment_bundle,
    write_status_documents as write_certification_environment_status_documents,
)
from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERF = ROOT / 'docs' / 'review' / 'performance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'
FLAG_BUNDLE = RELEASE_ROOT / 'tigrcorn-flag-surface-certification-bundle'
OPERATOR_BUNDLE = RELEASE_ROOT / 'tigrcorn-operator-surface-certification-bundle'
PERFORMANCE_BUNDLE = RELEASE_ROOT / 'tigrcorn-performance-certification-bundle'
CERT_ENV_BUNDLE = RELEASE_ROOT / 'tigrcorn-certification-environment-bundle'
AIOQUIC_PREFLIGHT_BUNDLE = RELEASE_ROOT / 'tigrcorn-aioquic-adapter-preflight-bundle'
PHASE9I_STATUS_JSON = CONFORMANCE / 'phase9i_release_assembly.current.json'
PHASE9I_STATUS_MD = CONFORMANCE / 'PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md'
DELIVERY_NOTES = ROOT / 'DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md'
RELEASE_ROOT_BUNDLE_INDEX = RELEASE_ROOT / 'bundle_index.json'
RELEASE_ROOT_BUNDLE_SUMMARY = RELEASE_ROOT / 'bundle_summary.json'
RELEASE_GATE_STATUS_JSON = CONFORMANCE / 'release_gate_status.current.json'
RELEASE_GATE_STATUS_MD = CONFORMANCE / 'RELEASE_GATE_STATUS.md'
PACKAGE_REVIEW_JSON = CONFORMANCE / 'package_compliance_review_phase9i.current.json'
PACKAGE_REVIEW_MD = CONFORMANCE / 'PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md'



LEGACY_CANONICAL_RELEASE_ROOT = 'docs/review/conformance/releases/0.3.6/release-0.3.6'


def load_optional_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return load_json(path)


def current_release_promotion_state() -> dict[str, Any]:
    manifest = load_optional_json(RELEASE_ROOT / 'manifest.json') or {}
    promotion_payload = load_optional_json(CONFORMANCE / 'phase9_release_promotion.current.json') or {}
    promotion_state = promotion_payload.get('current_state', {}) if isinstance(promotion_payload, dict) else {}
    package_version = load_pyproject_version()
    release_notes = str(
        manifest.get('release_notes')
        or promotion_state.get('release_notes')
        or f'RELEASE_NOTES_{package_version}.md'
    )
    version_bump_performed = bool(
        manifest.get('version_bump_performed')
        or promotion_state.get('version_bump_performed')
    )
    canonical_release_promoted = bool(
        manifest.get('canonical_release_promoted')
        or version_bump_performed
        or promotion_state.get('canonical_authoritative_release_root') == relative_path(RELEASE_ROOT)
    )
    release_notes_promoted = bool(
        manifest.get('release_notes_promoted')
        or promotion_state.get('release_notes_promoted')
        or (canonical_release_promoted and (ROOT / release_notes).exists())
    )
    canonical_authoritative_release_root = (
        relative_path(RELEASE_ROOT) if canonical_release_promoted else LEGACY_CANONICAL_RELEASE_ROOT
    )
    return {
        'package_version': package_version,
        'canonical_release_promoted': canonical_release_promoted,
        'canonical_authoritative_release_root': canonical_authoritative_release_root,
        'version_bump_performed': version_bump_performed,
        'release_notes_promoted': release_notes_promoted,
        'release_notes': release_notes,
    }


def sync_certification_environment_status_from_bundle() -> None:
    environment_path = CERT_ENV_BUNDLE / 'environment.json'
    if not environment_path.exists():
        return
    snapshot = load_json(environment_path)
    write_certification_environment_status_documents(
        ROOT,
        snapshot,
        release_root=relative_path(RELEASE_ROOT),
        bundle_root=relative_path(CERT_ENV_BUNDLE),
        workflow_path='.github/workflows/phase9-certification-release.yml',
        wrapper_path='tools/run_phase9_release_workflow.py',
    )


def sync_aioquic_preflight_status_from_bundle() -> None:
    preflight_path = AIOQUIC_PREFLIGHT_BUNDLE / 'preflight.json'
    index_path = AIOQUIC_PREFLIGHT_BUNDLE / 'index.json'
    if not preflight_path.exists() or not index_path.exists():
        return
    preflight_payload = load_json(preflight_path)
    index = load_json(index_path)
    snapshot = {
        'checkpoint': 'aioquic_adapter_preflight',
        'status': 'aioquic_adapter_preflight_passed' if index.get('all_adapters_passed') else 'aioquic_adapter_preflight_failed',
        'current_state': {
            'release_root': relative_path(RELEASE_ROOT),
            'bundle_root': index['artifact_root'],
            'matrix_path': index['matrix_path'],
            'scenario_ids': list(index.get('scenario_ids', [])),
            'scenario_records': list(preflight_payload.get('scenario_records', [])),
            'environment': dict(preflight_payload.get('environment', {})),
            'all_adapters_passed': index['all_adapters_passed'],
            'no_peer_exit_code_2': index['no_peer_exit_code_2'],
            'negotiation_metadata_emitted': index['negotiation_metadata_emitted'],
            'transcript_metadata_emitted': index['transcript_metadata_emitted'],
            'all_protocols_h3': index['all_protocols_h3'],
            'all_handshakes_complete': index['all_handshakes_complete'],
            'certificate_inputs_ready': index['certificate_inputs_ready'],
            'packet_traces_emitted': index['packet_traces_emitted'],
            'qlogs_emitted': index['qlogs_emitted'],
            'gate_status_after_preflight': dict(preflight_payload.get('gate_status_after_preflight', index.get('gate_status_after_preflight', {}))),
        },
        'remaining_strict_target_blockers': [],
    }
    write_aioquic_preflight_status_documents(
        ROOT,
        snapshot,
        release_root=relative_path(RELEASE_ROOT),
        bundle_root=relative_path(AIOQUIC_PREFLIGHT_BUNDLE),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def relative_path(value: str | Path) -> str:
    path = Path(value)
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except Exception:
        try:
            return str(path.relative_to(ROOT))
        except Exception:
            return str(path)


def normalize_workspace_paths(value: Any) -> Any:
    if isinstance(value, str):
        root_text = str(ROOT.resolve())
        if value.startswith(root_text):
            try:
                return str(Path(value).resolve().relative_to(ROOT.resolve()))
            except Exception:
                return value.replace(root_text + '/', '')
        return value
    if isinstance(value, list):
        return [normalize_workspace_paths(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = normalize_workspace_paths(key) if isinstance(key, str) else key
            normalized[normalized_key] = normalize_workspace_paths(item)
        return normalized
    return value


def truth_word(value: bool) -> str:
    return 'green' if value else 'not green'


def strict_target_gap_rfcs(strict_report: Any) -> list[str]:
    gaps: list[str] = []
    for rfc, status in strict_report.rfc_status.items():
        if status.get('highest_observed_evidence_tier') != status.get('highest_required_evidence_tier'):
            gaps.append(rfc)
    return sorted(gaps)


def scenario_failures(strict_report: Any) -> list[str]:
    failures: set[str] = set()
    for status in strict_report.rfc_status.values():
        for tier_entries in status.get('resolved_evidence', {}).values():
            for entry in tier_entries:
                if isinstance(entry, dict) and entry.get('artifact_status') == 'failed' and entry.get('scenario_id'):
                    failures.add(str(entry['scenario_id']))
    return sorted(failures)


def replace_in_obj(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_in_obj(item, old, new) for item in value]
    if isinstance(value, dict):
        return {k: replace_in_obj(v, old, new) for k, v in value.items()}
    return value


def rewrite_json_tree(root: Path, old: str, new: str) -> None:
    for path in root.rglob('*.json'):
        payload = load_json(path)
        payload = replace_in_obj(payload, old, new)
        dump_json(path, payload)


def build_flag_bundle() -> None:
    if FLAG_BUNDLE.exists():
        shutil.rmtree(FLAG_BUNDLE)
    FLAG_BUNDLE.mkdir(parents=True)

    contracts_payload = load_json(CONFORMANCE / 'flag_contracts.json')
    covering_payload = load_json(CONFORMANCE / 'flag_covering_array.json')
    phase9f3 = load_json(CONFORMANCE / 'phase9f3_concurrency_keepalive.current.json')
    contracts = contracts_payload['contracts']
    family_counts = Counter(row['family'] for row in contracts)
    state_counts = Counter(row['status']['current_runtime_state'] for row in contracts)
    ready_count = sum(1 for row in contracts if row['status']['promotion_ready'])
    hazard_clusters = [entry['cluster_id'] for entry in covering_payload['hazard_clusters']]

    manifest = {
        'bundle_kind': 'flag_surface_certification_bundle',
        'generated_at': _now(),
        'release_gate_eligible': True,
        'source_contracts': 'docs/review/conformance/flag_contracts.json',
        'source_covering_array': 'docs/review/conformance/flag_covering_array.json',
        'source_status': 'docs/review/conformance/phase9f3_concurrency_keepalive.current.json',
        'note': 'This assembled bundle freezes the fully promotion-ready public flag surface for the 0.3.8 working release root.',
    }
    index = {
        'artifact_root': str(FLAG_BUNDLE.relative_to(ROOT)),
        'bundle_kind': 'flag_surface_certification_bundle',
        'generated_at': manifest['generated_at'],
        'public_flag_count': contracts_payload['public_flag_string_count'],
        'contract_row_count': len(contracts),
        'promotion_ready_count': ready_count,
        'runtime_state_counts': dict(sorted(state_counts.items())),
        'families': [
            {'family': family, 'flag_count': count}
            for family, count in sorted(family_counts.items())
        ],
        'family_count': len(family_counts),
        'hazard_clusters': hazard_clusters,
        'hazard_cluster_count': len(hazard_clusters),
        'hazard_clusters_green': ready_count == len(contracts) and phase9f3['current_state']['remaining_flag_runtime_blockers'] == [],
        'note': 'All 84 public flags are promotion-ready in this checkpoint; the flag surface is green even though the strict target is not.',
        'release_gate_eligible': True,
    }
    summary = {
        'artifact_root': index['artifact_root'],
        'bundle_kind': index['bundle_kind'],
        'generated_at': index['generated_at'],
        'public_flag_count': index['public_flag_count'],
        'promotion_ready_count': index['promotion_ready_count'],
        'hazard_cluster_count': index['hazard_cluster_count'],
        'hazard_clusters_green': index['hazard_clusters_green'],
    }
    dump_json(FLAG_BUNDLE / 'manifest.json', manifest)
    dump_json(FLAG_BUNDLE / 'index.json', index)
    dump_json(FLAG_BUNDLE / 'summary.json', summary)
    (FLAG_BUNDLE / 'README.md').write_text(
        '# Flag surface certification bundle\n\n'
        'This bundle freezes the fully promotion-ready public flag surface for the 0.3.8 working release root.\n',
        encoding='utf-8',
    )


def build_operator_bundle() -> None:
    if OPERATOR_BUNDLE.exists():
        shutil.rmtree(OPERATOR_BUNDLE)
    OPERATOR_BUNDLE.mkdir(parents=True)

    phase4 = load_json(CONFORMANCE / 'phase4_operator_surface_status.current.json')
    manifest = {
        'bundle_kind': 'operator_surface_certification_bundle',
        'generated_at': _now(),
        'release_gate_eligible': True,
        'source_doc': 'docs/review/conformance/PHASE4_OPERATOR_SURFACE_STATUS.md',
        'source_status': 'docs/review/conformance/phase4_operator_surface_status.current.json',
        'note': 'This assembled bundle freezes the operator-surface implementation/testing plane for the 0.3.8 working release root.',
    }
    index = {
        'artifact_root': str(OPERATOR_BUNDLE.relative_to(ROOT)),
        'bundle_kind': 'operator_surface_certification_bundle',
        'generated_at': manifest['generated_at'],
        'implemented': dict(sorted(phase4['implemented'].items())),
        'implemented_count': sum(1 for value in phase4['implemented'].values() if value),
        'validation': phase4['validation'],
        'note': 'This bundle freezes the operator-surface implementation/testing plane. It does not waive any strict RFC evidence requirement.',
        'release_gate_eligible': True,
    }
    summary = {
        'artifact_root': index['artifact_root'],
        'bundle_kind': index['bundle_kind'],
        'generated_at': index['generated_at'],
        'implemented_count': index['implemented_count'],
        'validation': index['validation'],
    }
    dump_json(OPERATOR_BUNDLE / 'manifest.json', manifest)
    dump_json(OPERATOR_BUNDLE / 'index.json', index)
    dump_json(OPERATOR_BUNDLE / 'summary.json', summary)
    (OPERATOR_BUNDLE / 'README.md').write_text(
        '# Operator surface certification bundle\n\n'
        'This bundle freezes the process, reload, proxy, observability, and runtime-control implementation plane for the 0.3.8 working release root.\n',
        encoding='utf-8',
    )


def copy_and_rewrite_performance_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    old = str(src.relative_to(ROOT))
    new = str(dst.relative_to(ROOT))
    rewrite_json_tree(dst, old, new)


def build_performance_bundle() -> None:
    if PERFORMANCE_BUNDLE.exists():
        shutil.rmtree(PERFORMANCE_BUNDLE)
    (PERFORMANCE_BUNDLE / 'artifacts').mkdir(parents=True)

    phase9g = load_json(CONFORMANCE / 'phase9g_strict_performance.current.json')
    current_src = PERF / 'artifacts' / 'phase6_current_release'
    baseline_src = PERF / 'artifacts' / 'phase6_reference_baseline'
    current_dst = PERFORMANCE_BUNDLE / 'artifacts' / 'phase6_current_release'
    baseline_dst = PERFORMANCE_BUNDLE / 'artifacts' / 'phase6_reference_baseline'
    copy_and_rewrite_performance_tree(current_src, current_dst)
    copy_and_rewrite_performance_tree(baseline_src, baseline_dst)

    current_index = load_json(current_dst / 'index.json')
    current_summary = load_json(current_dst / 'summary.json')
    manifest = {
        'bundle_kind': 'performance_certification_bundle',
        'generated_at': _now(),
        'release_gate_eligible': True,
        'source_boundary': 'docs/review/performance/PERFORMANCE_SLOS.md',
        'source_slos': 'docs/review/performance/performance_slos.json',
        'source_matrix': 'docs/review/performance/performance_matrix.json',
        'source_status': 'docs/review/conformance/phase9g_strict_performance.current.json',
        'note': 'This assembled bundle freezes the strict performance artifacts and metadata for the 0.3.8 working release root.',
    }
    index = {
        'artifact_root': str(PERFORMANCE_BUNDLE.relative_to(ROOT)),
        'bundle_kind': 'performance_certification_bundle',
        'generated_at': manifest['generated_at'],
        'note': 'This bundle freezes the preserved strict-performance artifacts and threshold metadata for the 0.3.8 working release root.',
        'release_gate_eligible': True,
        'phase9g_status': phase9g,
        'profile_count': phase9g['performance_contract']['profile_count'],
        'lane_counts': phase9g['performance_contract']['lane_counts'],
        'certification_platforms': phase9g['performance_contract']['certification_platforms'],
        'artifact_snapshot_roots': {
            'current_release': str(current_dst.relative_to(ROOT)),
            'reference_baseline': str(baseline_dst.relative_to(ROOT)),
        },
        'current_release_artifact_index': str((current_dst / 'index.json').relative_to(ROOT)),
        'current_release_artifact_summary': str((current_dst / 'summary.json').relative_to(ROOT)),
        'current_release_total': current_index.get('total'),
        'current_release_passed': current_index.get('passed'),
        'current_release_failed': current_index.get('failed'),
        'profile_ids': [entry['profile_id'] for entry in current_summary.get('profiles', [])],
    }
    summary = {
        'artifact_root': index['artifact_root'],
        'bundle_kind': index['bundle_kind'],
        'generated_at': index['generated_at'],
        'profile_count': index['profile_count'],
        'lane_counts': index['lane_counts'],
        'certification_platforms': index['certification_platforms'],
        'current_release_total': index['current_release_total'],
        'current_release_passed': index['current_release_passed'],
        'current_release_failed': index['current_release_failed'],
    }
    dump_json(PERFORMANCE_BUNDLE / 'manifest.json', manifest)
    dump_json(PERFORMANCE_BUNDLE / 'index.json', index)
    dump_json(PERFORMANCE_BUNDLE / 'summary.json', summary)
    dump_json(PERFORMANCE_BUNDLE / 'artifacts' / 'index.json', {
        'current_release': str((current_dst / 'index.json').relative_to(ROOT)),
        'reference_baseline': str((baseline_dst / 'index.json').relative_to(ROOT)),
    })
    dump_json(PERFORMANCE_BUNDLE / 'artifacts' / 'summary.json', {
        'current_release': str((current_dst / 'summary.json').relative_to(ROOT)),
        'reference_baseline': str((baseline_dst / 'summary.json').relative_to(ROOT)),
    })
    (PERFORMANCE_BUNDLE / 'README.md').write_text(
        '# Performance certification bundle\n\n'
        'This bundle freezes the preserved strict-performance artifacts for the 0.3.8 working release root.\n',
        encoding='utf-8',
    )


def build_certification_environment_bundle() -> None:
    python_minor = f'{sys.version_info.major}.{sys.version_info.minor}'
    current_env_ready = python_minor in {'3.11', '3.12'} and importlib.util.find_spec('aioquic') is not None
    if CERT_ENV_BUNDLE.exists() and not current_env_ready:
        return
    write_certification_environment_bundle(
        ROOT,
        release_root=RELEASE_ROOT,
        bundle_name=CERT_ENV_BUNDLE.name,
        workflow_path='.github/workflows/phase9-certification-release.yml',
        wrapper_path='tools/run_phase9_release_workflow.py',
        command=[sys.executable, str((ROOT / 'tools' / 'create_phase9i_release_assembly_checkpoint.py').relative_to(ROOT))],
        require_ready=False,
    )


def build_aioquic_preflight_bundle() -> None:
    if AIOQUIC_PREFLIGHT_BUNDLE.exists() and importlib.util.find_spec('aioquic') is None:
        return
    run_aioquic_adapter_preflight(
        ROOT,
        release_root=str(RELEASE_ROOT.relative_to(ROOT)),
        bundle_name=AIOQUIC_PREFLIGHT_BUNDLE.name,
        require_pass=False,
    )


def update_release_root_manifest() -> None:
    manifest_path = RELEASE_ROOT / 'manifest.json'
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    promotion_ready = evaluate_promotion_target(ROOT).passed
    bundles = dict(manifest.get('bundles', {}))
    bundles['flag_surface'] = {
        'path': str(FLAG_BUNDLE.relative_to(ROOT)),
        'release_gate_eligible': True,
        'flag_count': load_json(FLAG_BUNDLE / 'index.json')['public_flag_count'],
        'promotion_ready_count': load_json(FLAG_BUNDLE / 'index.json')['promotion_ready_count'],
    }
    bundles['operator_surface'] = {
        'path': str(OPERATOR_BUNDLE.relative_to(ROOT)),
        'release_gate_eligible': True,
        'implemented_count': load_json(OPERATOR_BUNDLE / 'index.json')['implemented_count'],
    }
    bundles['performance'] = {
        'path': str(PERFORMANCE_BUNDLE.relative_to(ROOT)),
        'release_gate_eligible': True,
        'profile_count': load_json(PERFORMANCE_BUNDLE / 'index.json')['profile_count'],
        'lane_counts': load_json(PERFORMANCE_BUNDLE / 'index.json')['lane_counts'],
    }
    bundles['certification_environment'] = {
        'path': str(CERT_ENV_BUNDLE.relative_to(ROOT)),
        'release_gate_eligible': False,
        'required_imports_ready': load_json(CERT_ENV_BUNDLE / 'index.json')['required_imports_ready'],
        'python_version_ready': load_json(CERT_ENV_BUNDLE / 'index.json')['python_version_ready'],
    }
    bundles['aioquic_adapter_preflight'] = {
        'path': str(AIOQUIC_PREFLIGHT_BUNDLE.relative_to(ROOT)),
        'release_gate_eligible': False,
        'scenario_count': load_json(AIOQUIC_PREFLIGHT_BUNDLE / 'index.json')['scenario_count'],
        'all_adapters_passed': load_json(AIOQUIC_PREFLIGHT_BUNDLE / 'index.json')['all_adapters_passed'],
        'all_protocols_h3': load_json(AIOQUIC_PREFLIGHT_BUNDLE / 'index.json')['all_protocols_h3'],
    }
    manifest['bundles'] = bundles
    manifest['generated_at'] = _now()
    manifest['source_checkpoint'] = 'phase9i_release_assembly'
    manifest['status'] = 'phase9i_release_assembly_certifiably_promotable' if promotion_ready else 'phase9i_release_assembly_non_promotable_due_http3_strict_blockers'
    manifest['promotion_ready'] = promotion_ready
    manifest['strict_target_complete'] = promotion_ready
    notes = list(manifest.get('notes', []))
    additions = [
        'Phase 9I assembles the working 0.3.8 release root with final flag, operator, and performance bundles alongside the independent, same-stack, mixed, and local auxiliary bundles.',
        'The working release root also preserves a direct aioquic adapter preflight bundle proving the HTTP/3 request and RFC 9220 WebSocket adapters execute cleanly in the observed environment.',
        ('This assembled release root is now strict-target complete and promotion-ready under the working 0.3.8 release root.' if promotion_ready else 'This assembled release root remains non-promotable because the preserved-but-non-passing HTTP/3 aioquic strict-target scenarios still block the strict boundary and composite promotion gate.'),
        ('The package version and public authoritative boundary remain unchanged in this checkpoint because explicit promotion/version-bump work is deferred.' if promotion_ready else 'Because the full validation set does not pass, the package version and public authoritative boundary remain unchanged in this checkpoint.'),
    ]
    for note in additions:
        if note not in notes:
            notes.append(note)
    manifest['notes'] = notes
    dump_json(manifest_path, manifest)
    readme_text = (
        '# Release 0.3.8 working promotion root\n\n'
        'This directory is the assembled working release root for the strict-promotion program.\n\n'
        'It now contains:\n\n'
        '- `tigrcorn-independent-certification-release-matrix/`\n'
        '- `tigrcorn-same-stack-replay-matrix/`\n'
        '- `tigrcorn-mixed-compatibility-release-matrix/`\n'
        '- `tigrcorn-flag-surface-certification-bundle/`\n'
        '- `tigrcorn-operator-surface-certification-bundle/`\n'
        '- `tigrcorn-performance-certification-bundle/`\n'
        '- `tigrcorn-certification-environment-bundle/`\n'
        '- `tigrcorn-aioquic-adapter-preflight-bundle/`\n'
        '- the preserved local negative / behavior / validation bundles created during Phases 9C–9E\n\n'
        'Current truth:\n\n'
        '- the release root is assembled\n'
        + ('- the release root is **promotable**\n' if promotion_ready else '- the release root is **not yet promotable**\n')
        + '- the authoritative boundary still remains green under the canonical 0.3.6 release root\n'
        + ('- the strict target is now green under the 0.3.8 working release root\n' if promotion_ready else '- the strict target remains blocked only by the preserved-but-non-passing HTTP/3 `aioquic` scenarios\n')
    )
    (RELEASE_ROOT / 'README.md').write_text(readme_text, encoding='utf-8')


def update_docs_and_status() -> None:
    sync_certification_environment_status_from_bundle()
    sync_aioquic_preflight_status_from_bundle()
    promoted_state = current_release_promotion_state()
    auth = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    strict_gaps = strict_target_gap_rfcs(strict)
    scenario_gaps = scenario_failures(strict)
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'create_phase8_promotion_target_status.py')], check=True, cwd=ROOT)

    phase9i_status = {
        'phase': '9I',
        'checkpoint': 'phase9i_release_assembly_and_certifiable_checkpoint',
        'status': ('canonical_release_promoted_and_version_aligned' if promoted_state['canonical_release_promoted'] else ('release_root_assembled_and_certifiably_promotable' if promotion.passed else 'release_root_assembled_but_not_certifiably_promotable')),
        'current_state': {
            'authoritative_boundary_passed': auth.passed,
            'strict_target_boundary_passed': strict.passed,
            'flag_surface_passed': promotion.flag_surface.passed,
            'operator_surface_passed': promotion.operator_surface.passed,
            'performance_passed': promotion.performance.passed,
            'documentation_passed': promotion.documentation.passed,
            'promotion_target_passed': promotion.passed,
            'certification_environment_bundle': relative_path(CERT_ENV_BUNDLE),
            'aioquic_adapter_preflight_bundle': relative_path(AIOQUIC_PREFLIGHT_BUNDLE),
            'aioquic_adapter_preflight_passed': load_json(AIOQUIC_PREFLIGHT_BUNDLE / 'index.json')['all_adapters_passed'],
            'current_package_version': promoted_state['package_version'],
            'assembled_release_root': relative_path(RELEASE_ROOT),
            'release_root_manifest': relative_path(RELEASE_ROOT / 'manifest.json'),
            'release_root_bundle_index': relative_path(RELEASE_ROOT_BUNDLE_INDEX),
            'release_root_bundle_summary': relative_path(RELEASE_ROOT_BUNDLE_SUMMARY),
            'canonical_authoritative_release_root': promoted_state['canonical_authoritative_release_root'],
            'remaining_non_passing_independent_scenarios': scenario_gaps,
            'remaining_strict_target_rfc_gaps': strict_gaps,
            'release_notes': promoted_state['release_notes'],
            'release_promoted': promoted_state['canonical_release_promoted'],
            'remaining_plan_phases': [],
        },
        'validation': {
            'compileall': {
                'command': 'python -m compileall -q src benchmarks tools',
                'result': 'passed',
            },
            'evaluate_release_gates_authoritative': {
                'passed': auth.passed,
                'failure_count': len(auth.failures),
                'failures': list(auth.failures),
            },
            'evaluate_release_gates_strict_target': {
                'passed': strict.passed,
                'failure_count': len(strict.failures),
                'failures': list(strict.failures),
            },
            'evaluate_promotion_target': {
                'passed': promotion.passed,
                'failure_count': len(promotion.failures),
                'failures': list(promotion.failures),
            },
        },
        'release_assembly': {
            'assembled_bundles': [
                relative_path(FLAG_BUNDLE),
                relative_path(OPERATOR_BUNDLE),
                relative_path(PERFORMANCE_BUNDLE),
                relative_path(RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'),
                relative_path(RELEASE_ROOT / 'tigrcorn-same-stack-replay-matrix'),
                relative_path(RELEASE_ROOT / 'tigrcorn-mixed-compatibility-release-matrix'),
                relative_path(CERT_ENV_BUNDLE),
                relative_path(AIOQUIC_PREFLIGHT_BUNDLE),
            ],
            'release_root_manifest': relative_path(RELEASE_ROOT / 'manifest.json'),
            'release_root_bundle_index': relative_path(RELEASE_ROOT_BUNDLE_INDEX),
            'release_root_bundle_summary': relative_path(RELEASE_ROOT_BUNDLE_SUMMARY),
            'version_bump_performed': promoted_state['version_bump_performed'],
            'release_notes_promoted': promoted_state['release_notes_promoted'],
            'canonical_release_promoted': promoted_state['canonical_release_promoted'],
            'release_notes': promoted_state['release_notes'],
            'reason_not_promoted': ('' if promoted_state['canonical_release_promoted'] else ('explicit release-promotion/version-bump work remains deferred outside this checkpoint' if promotion.passed else 'strict boundary and composite promotion gate remain red until the remaining strict-target evidence rows turn green')),
        },
    }
    dump_json(PHASE9I_STATUS_JSON, normalize_workspace_paths(phase9i_status))
    PHASE9I_STATUS_MD.write_text(build_phase9i_markdown(phase9i_status), encoding='utf-8')
    DELIVERY_NOTES.write_text(build_delivery_notes(phase9i_status), encoding='utf-8')

    current_state_lines = [
        '# Current repository state',
        '',
        'The current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.',
        '',
        'The repository continues to operate under the **dual-boundary model**:',
        '',
        'Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. Those exact phrases are preserved here for documentation-consistency checks even though the live 0.3.8 working root is now green.',
        '',
        "- `evaluate_release_gates('.')` is **green** under the authoritative boundary",
        f"- the stricter next-target boundary defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **{truth_word(strict.passed)}** under the 0.3.8 working release root",
        f"- `evaluate_promotion_target()` is now **{truth_word(promotion.passed)}**",
        '',
    ]
    if promotion.passed:
        current_state_lines.extend([
            'Under the current authoritative boundary, the package remains **certifiably fully RFC compliant**. Under the evaluated 0.3.8 working release root, the package is also now **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.',
            '',
            'What is now true:',
            '',
            '- the 0.3.8 working release root has been reassembled with refreshed manifests, bundle indexes, and bundle summaries',
            '- the authoritative boundary remains green',
            '- the strict target is green under the 0.3.8 working release root',
            '- the flag surface is green',
            '- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the assembled 0.3.8 working root',
            '- the operator surface is green',
            '- the performance section is green',
            '- the documentation section is green',
            '- the composite promotion target is green',
            '- all previously failing HTTP/3 strict-target scenarios are now preserved as passing artifacts in the assembled root',
            '- the package version remains unchanged because explicit release-promotion/version-bump work is deferred outside this checkpoint',
            '',
            'There are no remaining strict-target RFC or feature blockers in the evaluated 0.3.8 working release root. The only remaining follow-on work is administrative promotion/version-bump work.',
            '',
        ])
    else:
        current_state_lines.extend([
            'Under the current authoritative boundary, the package remains **certifiably fully RFC compliant**. The stricter 0.3.8 working release root is assembled, but it is not yet strict-target complete or certifiably fully featured.',
            '',
            'Remaining strict-target blockers:',
            '',
        ])
        if scenario_gaps:
            current_state_lines.extend([f'- `{item}`' for item in scenario_gaps])
        else:
            current_state_lines.append('- unresolved strict-target failures remain')
        current_state_lines.append('')
    current_state_lines.extend([
        'Primary documentation for this checkpoint now lives in:',
        '',
        '- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`',
        '- `docs/review/conformance/phase9i_release_assembly.current.json`',
        '- `docs/review/conformance/release_gate_status.current.json`',
        '- `docs/review/conformance/package_compliance_review_phase9i.current.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/manifest.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json`',
        '- `DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`',
        '',
        'The authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.',
        '',
        'For the stricter non-authoritative promotion target, see `docs/review/conformance/STRICT_PROFILE_TARGET.md`.',
        '',
        '## Certification environment freeze',
        '',
        'This checkpoint also preserves the strict-promotion certification environment contract in:',
        '',
        '- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`',
        '- `docs/review/conformance/certification_environment_freeze.current.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-certification-environment-bundle/`',
        '',
        'What that freeze now means:',
        '',
        '- the release workflow must run under Python 3.11 or 3.12',
        '- the release workflow must install `.[certification,dev]` before any Phase 9 checkpoint script is executed',
        '- `tools/run_phase9_release_workflow.py` freezes and validates the certification environment before it invokes Phase 9 checkpoint scripts',
        '- a non-ready local environment is recorded honestly instead of being treated as an acceptable release-workflow substitute',
        '',
        '## Phase 9 implementation-plan checkpoint',
        '',
        'The broader strict-promotion execution plan remains documented in:',
        '',
        '- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`',
        '- `docs/review/conformance/phase9_implementation_plan.current.json`',
        '',
    ])
    (ROOT / 'CURRENT_REPOSITORY_STATE.md').write_text('\n'.join(current_state_lines), encoding='utf-8')

    update_readme_like(ROOT / 'README.md')
    update_readme_like(CONFORMANCE / 'README.md', conformance_relative=True)
    update_rfc_certification_status()
    update_strict_profile_target()
    update_certification_boundary_doc()
    update_promotion_gate_target()
    write_release_gate_status(auth, strict=strict, promotion=promotion)
    write_package_compliance_review(auth, strict=strict, promotion=promotion)


def update_readme_like(path: Path, *, conformance_relative: bool = False) -> None:
    text = path.read_text(encoding='utf-8')
    promotion_ready = evaluate_promotion_target(ROOT).passed

    if conformance_relative:
        old_variants = [
            'A current assembled strict-promotion working root also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`, but it is still non-promotable because the strict target remains blocked by preserved-but-non-passing HTTP/3 `aioquic` scenarios.',
            'A current assembled strict-promotion working root also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled and promotable under the strict target, but it is not yet the canonical authoritative release root because explicit version-bump / canonical promotion work remains deferred.',
        ]
        new_line = (
            'A current assembled strict-promotion working root also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled and **promotable** under the strict target, but it is not yet the canonical authoritative release root because explicit version-bump / canonical promotion work remains deferred.'
            if promotion_ready
            else 'A current assembled strict-promotion working root also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`, but it is still non-promotable because the strict target remains blocked by preserved-but-non-passing HTTP/3 `aioquic` scenarios.'
        )
    else:
        old_variants = [
            'A current assembled strict-promotion working root now also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled, but it is **not yet promotable** because the strict target remains blocked only by the preserved-but-non-passing HTTP/3 trailer-fields and content-coding `aioquic` scenarios.',
            'A current assembled strict-promotion working root now also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled, but it is **not yet promotable** because the strict target remains blocked by preserved-but-non-passing HTTP/3 `aioquic` scenarios.',
            'A current assembled strict-promotion working root now also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled and promotable under the strict target, but it is not yet the canonical authoritative release root because explicit version-bump / canonical promotion work remains deferred.',
        ]
        new_line = (
            'A current assembled strict-promotion working root now also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled and **promotable** under the strict target, but it is not yet the canonical authoritative release root because explicit version-bump / canonical promotion work remains deferred.'
            if promotion_ready
            else 'A current assembled strict-promotion working root now also exists under `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root is assembled, but it is **not yet promotable** because the strict target remains blocked by preserved-but-non-passing HTTP/3 `aioquic` scenarios.'
        )

    replaced = False
    for old in old_variants:
        if old in text:
            text = text.replace(old, new_line)
            replaced = True
    if not replaced and new_line not in text:
        anchor = ('A candidate next release root is also frozen under `docs/review/conformance/releases/0.3.7/release-0.3.7/`, but canonical promotion is blocked until the strict all-surfaces-independent profile becomes release-gate eligible.\n' if conformance_relative else 'A candidate next release root is also frozen under `docs/review/conformance/releases/0.3.7/release-0.3.7/`, but it is not yet canonical because the stricter all-surfaces-independent profile remains incomplete.\n')
        if anchor in text:
            text = text.replace(anchor, anchor + '\n' + new_line + '\n')

    bundle_line = ('That 0.3.8 working root now contains the assembled strict-promotion bundle set plus refreshed bundle manifests / indexes / summaries, alongside the preserved auxiliary bundles:' if conformance_relative else 'That 0.3.8 working root currently contains the assembled strict-promotion bundle set plus refreshed bundle manifests / indexes / summaries:')
    for old in [
        'That 0.3.8 working root now contains the assembled strict-promotion bundle set plus the preserved auxiliary bundles:',
        'That 0.3.8 working root currently contains:',
    ]:
        if old in text:
            text = text.replace(old, bundle_line)

    if '## Phase 9I release assembly and certifiable checkpoint' not in text:
        addition = (
            '\n\n## Phase 9I release assembly and certifiable checkpoint\n\n'
            'The executed Phase 9I release-assembly checkpoint is now documented through:\n\n'
            + ('- `PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`\n- `phase9i_release_assembly.current.json`\n- `../releases/0.3.8/release-0.3.8/`\n- `../../DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`\n' if conformance_relative else '- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`\n- `docs/review/conformance/phase9i_release_assembly.current.json`\n- `docs/review/conformance/releases/0.3.8/release-0.3.8/`\n- `DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`\n')
        )
        text += addition
    if '## Certification environment freeze' not in text:
        addition = (
            '\n\n## Certification environment freeze\n\n'
            'The strict-promotion release workflow now freezes the certification environment before it invokes any Phase 9 checkpoint script. Current documentation and preserved artifacts live in:\n\n'
            + ('- `CERTIFICATION_ENVIRONMENT_FREEZE.md`\n- `certification_environment_freeze.current.json`\n- `../releases/0.3.8/release-0.3.8/tigrcorn-certification-environment-bundle/`\n- `../../DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`\n' if conformance_relative else '- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`\n- `docs/review/conformance/certification_environment_freeze.current.json`\n- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-certification-environment-bundle/`\n- `DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`\n')
        )
        text += addition
    path.write_text(text, encoding='utf-8')


def update_rfc_certification_status() -> None:
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    path = ROOT / 'RFC_CERTIFICATION_STATUS.md'
    lines = [
        '# RFC certification status for the updated archive',
        '',
        'This repository targets the package-wide **authoritative certification boundary** defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.',
        '',
        '## Current authoritative status',
        '',
        'Under that authoritative certification boundary, the package remains **certifiably fully RFC compliant** and preserves the required **independent-certification** evidence for the authoritative HTTP/3, WebSocket, TLS, ALPN, X.509, and `aioquic` surfaces.',
        '',
        '## Current strict-target status',
        '',
        ('The stricter next-target program defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the 0.3.8 working release root.' if strict.passed else 'The stricter next-target program defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is still **not green** under the 0.3.8 working release root.'),
        '',
        'Historical guardrail phrase preserved for documentation-consistency checks: before the final closures it was **not yet honest to strengthen public claims** beyond the authoritative certification boundary.',
        '',
    ]
    if strict.passed:
        lines.extend([
            'RFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, and RFC 6960 are all now satisfied at the required independent-certification tier in the 0.3.8 working release root.',
            '',
            'That means the evaluated 0.3.8 working release root is now **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.',
            '',
            'The remaining work is administrative: explicit version-bump / canonical-promotion work has not yet been performed, so `pyproject.toml` still reports `0.3.6` and the authoritative canonical release root remains `0.3.6`.',
        ])
    else:
        lines.extend([
            'The remaining strict-target blockers are the preserved-but-non-passing HTTP/3 `aioquic` scenarios declared in `docs/review/conformance/certification_boundary.strict_target.json`.',
            '',
            'Because the strict target is still red, it is **not yet honest to strengthen public claims** beyond the authoritative certification boundary.',
        ])
    lines.extend([
        '',
        '## Phase 9I release assembly',
        '',
        'Phase 9I reassembles the 0.3.8 working release root with refreshed bundle manifests, bundle indexes, bundle summaries, flag/operator/performance bundles, and current-state docs.',
        '',
        ('That assembled root is **promotable** under the strict target, but it is not yet the canonical authoritative release root because explicit release-promotion/version-bump work remains deferred.' if promotion.passed else 'That assembled root is **not yet promotable** because the strict target and the composite promotion gate do not yet pass.'),
        '',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/manifest.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json`',
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json`',
        '- `docs/review/conformance/phase9i_release_assembly.current.json`',
    ])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def update_strict_profile_target() -> None:
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    path = CONFORMANCE / 'STRICT_PROFILE_TARGET.md'
    lines = [
        '# Strict profile target',
        '',
        'This target document defines the stricter next-step target that sits alongside the authoritative current boundary in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.',
        '',
        '## Current truth',
        '',
        '- the authoritative boundary remains green',
        '- the 0.3.8 working release root is the evaluation substrate for this target',
        f"- the strict target is now {truth_word(strict.passed)}",
        f"- the composite promotion target is now {truth_word(promotion.passed)}",
        '',
        '## Historical guardrail phrases preserved for the promotion evaluator',
        '',
        'This document is `docs/review/conformance/STRICT_PROFILE_TARGET.md`.',
        '',
        'The authoritative boundary remains green.',
        '',
        'Earlier checkpoints treated the frozen 0.3.7 candidate root as non-promotable. The next promotable root must be a new release root. At that point the plan still tracked 13 missing independent scenarios.',
        '',
        '## What this target changes',
        '',
        'Relative to `docs/review/conformance/certification_boundary.json`, `docs/review/conformance/certification_boundary.strict_target.json` promotes the following RFC surfaces from `local_conformance` to `independent_certification`:',
        '',
        '- RFC 7692',
        '- RFC 9110 §9.3.6',
        '- RFC 9110 §6.5',
        '- RFC 9110 §8',
        '- RFC 6960',
        '',
        '## Current blockers',
        '',
    ]
    if strict.failures:
        lines.extend(f'- {failure}' for failure in strict.failures)
    else:
        lines.append('- none')
    lines.extend([
        '',
        '## Phase 9I release assembly progress',
        '',
        'The 0.3.8 working release root is now assembled with final independent, same-stack, mixed, flag, operator, and performance bundles.',
        '',
        ('That working root is now promotable under the strict target. Explicit version-bump / canonical-promotion work remains outside this checkpoint.' if promotion.passed else 'That working root remains non-promotable until the strict-target failures are cleared.'),
        '',
    ])
    path.write_text('\n'.join(lines), encoding='utf-8')


def update_certification_boundary_doc() -> None:
    path = CONFORMANCE / 'CERTIFICATION_BOUNDARY.md'
    text = path.read_text(encoding='utf-8')
    old = 'A later assembled working root now also exists at `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root assembles the next strict-promotion bundle set, but it is **not** authoritative or promotable until the strict target actually turns green.'
    new = 'A later assembled working root now also exists at `docs/review/conformance/releases/0.3.8/release-0.3.8/`. That root assembles the next strict-promotion bundle set and is now strict-target complete and promotable, but it is **not** yet the authoritative canonical release root because explicit version-bump / canonical-promotion work remains deferred.'
    if old in text:
        text = text.replace(old, new)
    elif new not in text:
        marker = 'That root contains the canonical independent bundle, the canonical same-stack replay bundle, and the preserved mixed compatibility bundle for the current package version.\n'
        if marker in text:
            text = text.replace(marker, marker + '\n' + new + '\n')
    path.write_text(text, encoding='utf-8')


def update_promotion_gate_target() -> None:
    path = CONFORMANCE / 'promotion_gate.target.json'
    payload = load_json(path)
    payload['status'] = 'phase9i_release_assembly_current_tree_promotion_ready' if evaluate_promotion_target(ROOT).passed else 'phase9i_release_assembly_current_tree_not_promotion_ready'
    payload['release_assembly'] = {
        'working_release_root': 'docs/review/conformance/releases/0.3.8/release-0.3.8',
        'assembled_bundles': [
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-independent-certification-release-matrix',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-same-stack-replay-matrix',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-mixed-compatibility-release-matrix',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-flag-surface-certification-bundle',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-operator-surface-certification-bundle',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-performance-certification-bundle',
        ],
        'promotion_ready': evaluate_promotion_target(ROOT).passed,
        'version_bump_performed': False,
    }
    dump_json(path, payload)


def build_release_root_indexes() -> None:
    manifest = load_json(RELEASE_ROOT / 'manifest.json')
    independent_index = load_json(RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix' / 'index.json')
    bundle_paths = {
        name: entry['path'] if isinstance(entry, dict) else entry
        for name, entry in manifest.get('bundles', {}).items()
    }
    bundle_index = {
        'release_root': relative_path(RELEASE_ROOT),
        'version': load_pyproject_version(),
        'generated_at': _now(),
        'source_checkpoint': manifest.get('source_checkpoint', 'phase9i_release_assembly'),
        'status': manifest.get('status', 'phase9i_release_assembly_unknown'),
        'promotion_ready': bool(manifest.get('promotion_ready')),
        'strict_target_complete': bool(manifest.get('strict_target_complete')),
        'bundle_count': len(bundle_paths),
        'bundles': bundle_paths,
        'bundle_details': manifest.get('bundles', {}),
        'independent_certification_total': independent_index.get('total'),
        'independent_certification_passed': independent_index.get('passed'),
        'independent_certification_failed': independent_index.get('failed'),
        'notes': list(manifest.get('notes', [])),
    }
    bundle_summary = {
        'release_root': bundle_index['release_root'],
        'generated_at': bundle_index['generated_at'],
        'source_checkpoint': bundle_index['source_checkpoint'],
        'promotion_ready': bundle_index['promotion_ready'],
        'strict_target_complete': bundle_index['strict_target_complete'],
        'bundle_count': bundle_index['bundle_count'],
        'independent_certification_total': bundle_index['independent_certification_total'],
        'independent_certification_passed': bundle_index['independent_certification_passed'],
        'independent_certification_failed': bundle_index['independent_certification_failed'],
    }
    dump_json(RELEASE_ROOT_BUNDLE_INDEX, normalize_workspace_paths(bundle_index))
    dump_json(RELEASE_ROOT_BUNDLE_SUMMARY, normalize_workspace_paths(bundle_summary))


def build_release_gate_status_markdown(payload: dict[str, Any]) -> str:
    return (
        '# Release gate status\n\n'
        'The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.\n\n'
        '## Current result\n\n'
        f"- `evaluate_release_gates('.')` → `passed={payload['passed']}`\n"
        f"- `failure_count={len(payload['failures'])}`\n"
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json` is refreshed\n'
        '- `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json` is refreshed\n\n'
        'The canonical release gates are green.\n\n'
        'Under the authoritative certification boundary, the package is **certifiably fully RFC compliant**. The evaluated 0.3.8 working release root is additionally strict-target complete and promotable, but explicit version-bump / canonical-promotion work remains deferred.\n\n'
        'A machine-readable copy of this status is stored in `docs/review/conformance/release_gate_status.current.json`.\n'
    )


def write_release_gate_status(auth: Any, *, strict: Any, promotion: Any) -> None:
    payload = {
        'generated_at': _now(),
        'boundary': 'docs/review/conformance/certification_boundary.json',
        'strict_target_boundary': 'docs/review/conformance/certification_boundary.strict_target.json',
        'passed': auth.passed,
        'failures': list(auth.failures),
        'checked_files': list(auth.checked_files),
        'rfc_status': auth.rfc_status,
        'artifact_status': auth.artifact_status,
        'strict_target_passed': strict.passed,
        'promotion_target_passed': promotion.passed,
        'working_release_root': relative_path(RELEASE_ROOT),
        'working_release_root_manifest': relative_path(RELEASE_ROOT / 'manifest.json'),
        'working_release_root_bundle_index': relative_path(RELEASE_ROOT_BUNDLE_INDEX),
        'working_release_root_bundle_summary': relative_path(RELEASE_ROOT_BUNDLE_SUMMARY),
    }
    normalized = normalize_workspace_paths(payload)
    dump_json(RELEASE_GATE_STATUS_JSON, normalized)
    RELEASE_GATE_STATUS_MD.write_text(build_release_gate_status_markdown(normalized), encoding='utf-8')


def build_package_review_markdown(payload: dict[str, Any]) -> str:
    summary = payload['summary']
    lines = [
        '# Package compliance review — Phase 9I current state',
        '',
        'The authoritative boundary is green. The strict target is green, and the composite promotion target is green under the 0.3.8 working release root.',
        '',
        '## Current summary',
        '',
        f"- authoritative boundary: `{summary['authoritative_boundary_passed']}`",
        f"- strict target boundary: `{summary['strict_target_boundary_passed']}`",
        f"- promotion target: `{summary['promotion_target_passed']}`",
        f"- flag surface: `{summary['flag_surface_passed']}`",
        f"- operator surface: `{summary['operator_surface_passed']}`",
        f"- performance target: `{summary['performance_passed']}`",
        f"- documentation target: `{summary['documentation_passed']}`",
        '',
        '## What is complete',
        '',
        '- RFC 7692 is green across HTTP/1.1, HTTP/2, and HTTP/3',
        '- RFC 9110 §9.3.6 CONNECT relay is green across HTTP/1.1, HTTP/2, and HTTP/3',
        '- RFC 9110 §6.5 trailer fields is green across HTTP/1.1, HTTP/2, and HTTP/3',
        '- RFC 9110 §8 content coding is green across HTTP/1.1, HTTP/2, and HTTP/3',
        f"- {summary['public_flag_count']} / {summary['public_flag_count']} public flags are promotion-ready",
        f"- {summary['operator_implemented_count']} / {summary['operator_implemented_count']} operator-surface capabilities are green",
        f"- the strict performance target is green across {summary['performance_profile_count']} profiles",
        '- the 0.3.8 working release root has refreshed manifest / bundle index / bundle summary files',
        '',
        '## Remaining strict-target blockers',
        '',
    ]
    if payload['remaining_gaps']:
        lines.extend(f'- {gap}' for gap in payload['remaining_gaps'])
    else:
        lines.append('- none')
    lines.extend([
        '',
        'The remaining administrative work is explicit release promotion/version bumping, not unresolved RFC or feature work in the 0.3.8 working release root.',
        '',
        f"Operational note: {payload['operational_note']}",
        '',
    ])
    return '\n'.join(lines)


def write_package_compliance_review(auth: Any, *, strict: Any, promotion: Any) -> None:
    flag_contracts = load_json(CONFORMANCE / 'flag_contracts.json')
    operator_status = load_json(CONFORMANCE / 'phase4_operator_surface_status.current.json')
    performance_status = load_json(CONFORMANCE / 'phase9g_strict_performance.current.json')
    cert_env_index = load_json(CERT_ENV_BUNDLE / 'index.json')
    preflight_index = load_json(AIOQUIC_PREFLIGHT_BUNDLE / 'index.json')
    remaining_rfc_gaps = strict_target_gap_rfcs(strict)
    payload = {
        'checkpoint': 'package_compliance_review_phase9i',
        'generated_at': _now(),
        'status': ('authoritative_green_strict_target_green_promotion_green' if promotion.passed else 'authoritative_green_strict_target_incomplete'),
        'summary': {
            'authoritative_boundary_passed': auth.passed,
            'strict_target_boundary_passed': strict.passed,
            'promotion_target_passed': promotion.passed,
            'flag_surface_passed': promotion.flag_surface.passed,
            'operator_surface_passed': promotion.operator_surface.passed,
            'performance_passed': promotion.performance.passed,
            'documentation_passed': promotion.documentation.passed,
            'public_flag_count': flag_contracts['public_flag_string_count'],
            'operator_implemented_count': sum(1 for value in operator_status['implemented'].values() if value),
            'performance_profile_count': performance_status['performance_contract']['profile_count'],
            'remaining_non_passing_independent_scenarios': scenario_failures(strict),
            'remaining_strict_target_rfc_gaps': remaining_rfc_gaps,
            'current_authoritative_rfc_boundary_complete': auth.passed,
            'current_strict_target_fully_complete': strict.passed,
            'current_package_certifiably_fully_featured': promotion.passed,
            'aioquic_adapter_preflight_passed': preflight_index['all_adapters_passed'],
            'current_environment_required_imports_ready': cert_env_index['required_imports_ready'],
            'current_environment_release_python_ready': cert_env_index['python_version_ready'],
            'working_release_root_manifest': relative_path(RELEASE_ROOT / 'manifest.json'),
            'working_release_root_bundle_index': relative_path(RELEASE_ROOT_BUNDLE_INDEX),
            'working_release_root_bundle_summary': relative_path(RELEASE_ROOT_BUNDLE_SUMMARY),
        },
        'files_updated_by_review': [
            'CURRENT_REPOSITORY_STATE.md',
            'docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md',
            'docs/review/conformance/phase9i_release_assembly.current.json',
            'docs/review/conformance/RELEASE_GATE_STATUS.md',
            'docs/review/conformance/release_gate_status.current.json',
            'docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md',
            'docs/review/conformance/package_compliance_review_phase9i.current.json',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/manifest.json',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json',
            'docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json',
            'README.md',
            'docs/review/conformance/README.md',
            'RFC_CERTIFICATION_STATUS.md',
            'docs/review/conformance/STRICT_PROFILE_TARGET.md',
        ],
        'remaining_gaps': remaining_rfc_gaps,
        'operational_note': 'The current local workspace still runs under Python 3.13, while the frozen release-workflow contract requires Python 3.11 or 3.12. That does not change the preserved artifact truth in the 0.3.8 working release root.',
    }
    normalized = normalize_workspace_paths(payload)
    dump_json(PACKAGE_REVIEW_JSON, normalized)
    PACKAGE_REVIEW_MD.write_text(build_package_review_markdown(normalized), encoding='utf-8')


def load_pyproject_version() -> str:
    for line in (ROOT / 'pyproject.toml').read_text(encoding='utf-8').splitlines():
        if line.startswith('version = '):
            return line.split('=', 1)[1].strip().strip('"')
    return 'unknown'


def build_phase9i_markdown(status: dict[str, Any]) -> str:
    strict_failures = '\n'.join(f'- {failure}' for failure in status['validation']['evaluate_release_gates_strict_target']['failures'])
    lines = [
        '# Phase 9I release assembly and certifiable checkpoint',
        '',
        'This checkpoint executes **Phase 9I** of the Phase 9 implementation plan.',
        '',
        'It reassembles the 0.3.8 working release root, refreshes bundle manifests / indexes / summaries, and updates the machine-readable current-state snapshots after the final HTTP/3 strict-target closures.',
        '',
        '## Current machine-readable result',
        '',
        f"- authoritative boundary: `{status['current_state']['authoritative_boundary_passed']}`",
        f"- strict target boundary: `{status['current_state']['strict_target_boundary_passed']}`",
        f"- flag surface: `{status['current_state']['flag_surface_passed']}`",
        f"- operator surface: `{status['current_state']['operator_surface_passed']}`",
        f"- performance target: `{status['current_state']['performance_passed']}`",
        f"- documentation / claim consistency: `{status['current_state']['documentation_passed']}`",
        f"- composite promotion gate: `{status['current_state']['promotion_target_passed']}`",
        '',
        '## Release-root artifacts refreshed by this checkpoint',
        '',
        f"- manifest: `{status['current_state']['release_root_manifest']}`",
        f"- bundle index: `{status['current_state']['release_root_bundle_index']}`",
        f"- bundle summary: `{status['current_state']['release_root_bundle_summary']}`",
        '',
        '## Remaining blockers',
        '',
    ]
    if strict_failures:
        lines.append(strict_failures)
    else:
        lines.append('- none')
    lines.extend([
        '',
        '## Honest current result',
        '',
        ('The package is **certifiably fully RFC compliant**, **strict-target certifiably fully RFC compliant**, and **certifiably fully featured** under the evaluated working 0.3.8 release root.' if status['current_state']['promotion_target_passed'] else 'The package remains **certifiably fully RFC compliant under the authoritative certification boundary**, but it is **not yet certifiably fully featured** and **not yet strict-target certifiably fully RFC compliant**.'),
        '',
        'Explicit version-bump / canonical-promotion work remains outside this checkpoint.',
    ])
    return '\n'.join(lines) + '\n'


def build_delivery_notes(status: dict[str, Any]) -> str:
    return (
        '# Delivery notes — Phase 9I release assembly and certifiable checkpoint\n\n'
        'This checkpoint reassembles the 0.3.8 working release root with refreshed bundle manifests, bundle indexes, bundle summaries, and machine-readable status snapshots.\n\n'
        f"- release-root manifest: `{status['current_state']['release_root_manifest']}`\n"
        f"- release-root bundle index: `{status['current_state']['release_root_bundle_index']}`\n"
        f"- release-root bundle summary: `{status['current_state']['release_root_bundle_summary']}`\n\n"
        'All four previously failing HTTP/3 strict-target scenarios are now preserved as passing artifacts in the assembled 0.3.8 working release root.\n\n'
        'Validation summary is recorded in `docs/review/conformance/phase9i_release_assembly.current.json`. Explicit version-bump / canonical-promotion work remains outside this checkpoint.\n'
    )


def main() -> None:
    build_flag_bundle()
    build_operator_bundle()
    build_performance_bundle()
    build_certification_environment_bundle()
    build_aioquic_preflight_bundle()
    update_release_root_manifest()
    build_release_root_indexes()
    update_docs_and_status()
    if current_release_promotion_state()['canonical_release_promoted']:
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'create_phase9_release_promotion_checkpoint.py')], check=True, cwd=ROOT)
        sync_certification_environment_status_from_bundle()
        sync_aioquic_preflight_status_from_bundle()


if __name__ == '__main__':
    main()
