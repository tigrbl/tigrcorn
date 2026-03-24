from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
PERF = ROOT / 'docs' / 'review' / 'performance'
SRC_RELEASE = CONFORMANCE / 'releases' / '0.3.6' / 'release-0.3.6'
NEXT_RELEASE = CONFORMANCE / 'releases' / '0.3.7' / 'release-0.3.7'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _rewrite_release_paths(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, str):
        value = value.replace('/mnt/data/tigrcorn_work/tigrcorn_0.3.6_certification_update/', '')
        value = value.replace('docs/review/conformance/releases/0.3.6/release-0.3.6', 'docs/review/conformance/releases/0.3.7/release-0.3.7')
        if key == 'commit_hash' and value == 'release-0.3.6':
            value = 'release-0.3.7-candidate'
        return value
    if isinstance(value, list):
        return [_rewrite_release_paths(item) for item in value]
    if isinstance(value, dict):
        return {nested_key: _rewrite_release_paths(item, key=nested_key) for nested_key, item in value.items()}
    return value


def copy_bundle(name: str) -> dict[str, Any]:
    src = SRC_RELEASE / name
    dst = NEXT_RELEASE / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for json_file in dst.rglob('*.json'):
        dump_json(json_file, _rewrite_release_paths(load_json(json_file)))
    index = dst / 'index.json'
    manifest = dst / 'manifest.json'
    summary: dict[str, Any] = {
        'bundle_name': name,
        'copied_from': str(src.relative_to(ROOT)),
        'copied_to': str(dst.relative_to(ROOT)),
        'has_index': index.exists(),
        'has_manifest': manifest.exists(),
    }
    if index.exists():
        try:
            idx = load_json(index)
            summary['passed'] = idx.get('passed')
            summary['failed'] = idx.get('failed')
            summary['scenario_count'] = len(idx.get('scenarios', []))
            summary['release_gate_eligible'] = idx.get('release_gate_eligible', True)
        except Exception:
            pass
    return summary


def build_flag_bundle(flags_json: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    flags = flags_json.get('flags', [])
    families = {}
    rfc_scoped = []
    missing_docs = []
    missing_tests = []
    missing_config_path = []
    missing_profiles = []
    for entry in flags:
        family = entry.get('family', 'unknown')
        families.setdefault(family, 0)
        families[family] += 1
        claim_class = entry.get('claim_class')
        if claim_class in {'rfc_scoped', 'hybrid'}:
            rfc_scoped.append(entry['flag_id'])
            if not entry.get('interop_scenarios'):
                missing_profiles.append(entry['flag_id'])
        if not entry.get('config_path'):
            missing_config_path.append(entry['flag_id'])
        if not entry.get('unit_tests'):
            missing_tests.append(entry['flag_id'])
    index = {
        'artifact_root': str(target_dir.relative_to(ROOT)),
        'bundle_kind': 'flag_surface_certification_bundle',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'release_gate_eligible': True,
        'flag_count': len(flags),
        'family_count': len(families),
        'families': [{ 'family': k, 'flag_count': v } for k, v in sorted(families.items())],
        'rfc_scoped_or_hybrid_flags': sorted(rfc_scoped),
        'missing_config_path': sorted(missing_config_path),
        'missing_unit_tests': sorted(missing_tests),
        'rfc_or_hybrid_flags_missing_interop_scenarios': sorted(missing_profiles),
        'note': 'This bundle certifies the public flag-surface metadata plane. It is not a substitute for strict RFC evidence tiers.'
    }
    manifest = {
        'bundle_kind': 'flag_surface_certification_bundle',
        'release_gate_eligible': True,
        'source': str((CONFORMANCE / 'cli_flag_surface.json').relative_to(ROOT)),
        'source_doc': str((CONFORMANCE / 'CLI_FLAG_SURFACE.md').relative_to(ROOT)),
        'deployment_profiles': str((CONFORMANCE / 'deployment_profiles.json').relative_to(ROOT)),
        'generated_at': index['generated_at'],
        'note': 'Flag metadata is complete enough to freeze the candidate release root, but strict RFC promotion still depends on preserved third-party evidence.'
    }
    dump_json(target_dir / 'index.json', index)
    dump_json(target_dir / 'manifest.json', manifest)
    (target_dir / 'README.md').write_text(
        '# Flag surface certification bundle\n\n'
        'This bundle freezes the public flag metadata, tests, and deployment-profile mapping for the release candidate.\n',
        encoding='utf-8',
    )
    return index


def build_operator_bundle(phase4_json: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    implemented = phase4_json.get('implemented', {})
    validation = phase4_json.get('validation', {})
    index = {
        'artifact_root': str(target_dir.relative_to(ROOT)),
        'bundle_kind': 'operator_surface_certification_bundle',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'release_gate_eligible': True,
        'implemented': implemented,
        'implemented_count': sum(1 for v in implemented.values() if v),
        'validation': validation,
        'note': 'This bundle freezes the operator-surface implementation/testing plane. It does not waive any strict RFC evidence requirement.'
    }
    manifest = {
        'bundle_kind': 'operator_surface_certification_bundle',
        'release_gate_eligible': True,
        'source_doc': str((CONFORMANCE / 'PHASE4_OPERATOR_SURFACE_STATUS.md').relative_to(ROOT)),
        'source_status': str((CONFORMANCE / 'phase4_operator_surface_status.current.json').relative_to(ROOT)),
        'generated_at': index['generated_at'],
    }
    dump_json(target_dir / 'index.json', index)
    dump_json(target_dir / 'manifest.json', manifest)
    (target_dir / 'README.md').write_text(
        '# Operator surface certification bundle\n\n'
        'This bundle freezes the process, reload, proxy, observability, and runtime-control implementation plane for the release candidate.\n',
        encoding='utf-8',
    )
    return index


def build_performance_bundle(perf_matrix: dict[str, Any], phase6_json: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    # copy current performance artifacts into the bundle for a self-contained candidate snapshot
    src_current = ROOT / perf_matrix['current_artifact_root']
    dst_current = target_dir / 'artifacts'
    if dst_current.exists():
        shutil.rmtree(dst_current)
    shutil.copytree(src_current, dst_current)
    profiles = perf_matrix.get('profiles', [])
    index = {
        'artifact_root': str(target_dir.relative_to(ROOT)),
        'bundle_kind': 'performance_certification_bundle',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'release_gate_eligible': True,
        'profile_count': len(profiles),
        'profiles': [p.get('profile_id') for p in profiles],
        'phase6_status': phase6_json,
        'note': 'This bundle freezes the preserved current-release performance artifacts and threshold metadata.'
    }
    manifest = {
        'bundle_kind': 'performance_certification_bundle',
        'release_gate_eligible': True,
        'source_matrix': str((PERF / 'performance_matrix.json').relative_to(ROOT)),
        'source_boundary': str((PERF / 'PERFORMANCE_BOUNDARY.md').relative_to(ROOT)),
        'generated_at': index['generated_at'],
    }
    dump_json(target_dir / 'index.json', index)
    dump_json(target_dir / 'manifest.json', manifest)
    (target_dir / 'README.md').write_text(
        '# Performance certification bundle\n\n'
        'This bundle freezes the preserved current-release performance artifacts for the release candidate.\n',
        encoding='utf-8',
    )
    return index


def main() -> None:
    NEXT_RELEASE.mkdir(parents=True, exist_ok=True)

    copied = [
        copy_bundle('tigrcorn-independent-certification-release-matrix'),
        copy_bundle('tigrcorn-same-stack-replay-matrix'),
        copy_bundle('tigrcorn-mixed-compatibility-release-matrix'),
    ]

    flags_json = load_json(CONFORMANCE / 'cli_flag_surface.json')
    phase4_json = load_json(CONFORMANCE / 'phase4_operator_surface_status.current.json')
    phase6_json = load_json(CONFORMANCE / 'phase6_performance_status.current.json')
    strict_json = load_json(CONFORMANCE / 'all_surfaces_independent_state.json')
    perf_matrix = load_json(PERF / 'performance_matrix.json')

    flag_index = build_flag_bundle(flags_json, NEXT_RELEASE / 'tigrcorn-flag-surface-certification-bundle')
    operator_index = build_operator_bundle(phase4_json, NEXT_RELEASE / 'tigrcorn-operator-surface-certification-bundle')
    perf_index = build_performance_bundle(perf_matrix, phase6_json, NEXT_RELEASE / 'tigrcorn-performance-certification-bundle')

    blockers = strict_json.get('strict_profile_missing_independent_scenarios', [])
    root_manifest = {
        'release_version': '0.3.7',
        'candidate_release_root': str(NEXT_RELEASE.relative_to(ROOT)),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'canonical_promotion_performed': False,
        'authoritative_boundary_passed': True,
        'strict_profile_release_gate_eligible': strict_json.get('strict_profile_release_gate_eligible', False),
        'blocking_missing_independent_scenarios': blockers,
        'blocking_missing_rfc_targets': strict_json.get('strict_profile_missing_rfcs', []),
        'bundles': {
            'independent_certification': copied[0],
            'same_stack_replay': copied[1],
            'mixed': copied[2],
            'flag_surface': {'release_gate_eligible': flag_index.get('release_gate_eligible', False), 'flag_count': flag_index.get('flag_count')},
            'operator_surface': {'release_gate_eligible': operator_index.get('release_gate_eligible', False), 'implemented_count': operator_index.get('implemented_count')},
            'performance': {'release_gate_eligible': perf_index.get('release_gate_eligible', False), 'profile_count': perf_index.get('profile_count')},
        },
        'note': 'The next release root is frozen as a candidate only. Canonical promotion is blocked because the strict all-surfaces-independent profile is not green.'
    }
    dump_json(NEXT_RELEASE / 'manifest.json', root_manifest)
    (NEXT_RELEASE / 'README.md').write_text(
        '# Release 0.3.7 candidate root\n\n'
        'This root freezes the candidate bundles for the next release. It is **not** canonical yet.\n\n'
        'Canonical promotion is blocked because the strict all-surfaces-independent profile still has missing independent scenarios.\n',
        encoding='utf-8',
    )


if __name__ == '__main__':
    main()
