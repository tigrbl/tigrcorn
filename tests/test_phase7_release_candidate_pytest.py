from __future__ import annotations

import json
from pathlib import Path


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def test_phase7_status_snapshot_records_blocked_promotion() -> None:
    status = load_json('docs/review/conformance/phase7_canonical_promotion_status.current.json')
    assert status['phase'] == 7
    assert status['canonical_promotion_performed'] is False
    assert status['authoritative_boundary_passed'] is True
    assert status['strict_overlay_passed'] is False
    assert status['strict_profile_release_gate_eligible'] is False
    assert len(status['blocking_missing_independent_scenarios']) == 13


def test_phase7_candidate_release_root_contains_required_bundles() -> None:
    root = Path('docs/review/conformance/releases/0.3.7/release-0.3.7')
    assert root.exists()
    required = {
        'tigrcorn-independent-certification-release-matrix',
        'tigrcorn-same-stack-replay-matrix',
        'tigrcorn-mixed-compatibility-release-matrix',
        'tigrcorn-flag-surface-certification-bundle',
        'tigrcorn-operator-surface-certification-bundle',
        'tigrcorn-performance-certification-bundle',
    }
    assert required.issubset({p.name for p in root.iterdir() if p.is_dir()})
    manifest = load_json(str(root / 'manifest.json'))
    assert manifest['canonical_promotion_performed'] is False
    assert manifest['strict_profile_release_gate_eligible'] is False


def test_phase7_candidate_flag_operator_performance_bundles_are_frozen() -> None:
    root = Path('docs/review/conformance/releases/0.3.7/release-0.3.7')
    flag_index = load_json(str(root / 'tigrcorn-flag-surface-certification-bundle' / 'index.json'))
    operator_index = load_json(str(root / 'tigrcorn-operator-surface-certification-bundle' / 'index.json'))
    perf_index = load_json(str(root / 'tigrcorn-performance-certification-bundle' / 'index.json'))

    assert flag_index['release_gate_eligible'] is True
    assert flag_index['flag_count'] > 0
    assert operator_index['release_gate_eligible'] is True
    assert operator_index['implemented_count'] >= 1
    assert perf_index['release_gate_eligible'] is True
    assert perf_index['profile_count'] >= 1


def test_phase7_docs_keep_current_boundary_canonical() -> None:
    current_state = Path('docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md').read_text(encoding='utf-8')
    boundary_doc = Path('docs/review/conformance/CERTIFICATION_BOUNDARY.md').read_text(encoding='utf-8')
    phase7_doc = Path('docs/review/conformance/PHASE7_CANONICAL_PROMOTION_STATUS.md').read_text(encoding='utf-8')
    assert 'Canonical promotion was **not** performed' in current_state
    assert 'candidate next release root' in boundary_doc
    assert 'cannot honestly replace `certification_boundary.json`' in phase7_doc
