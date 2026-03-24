from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_phase9i_docs_and_status_exist() -> None:
    assert (CONFORMANCE / 'PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md').exists()
    assert (CONFORMANCE / 'phase9i_release_assembly.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md').exists()

    status = load_json(CONFORMANCE / 'phase9i_release_assembly.current.json')
    assert status['phase'] == '9I'
    assert status['checkpoint'] == 'phase9i_release_assembly_and_certifiable_checkpoint'
    assert status['current_state']['authoritative_boundary_passed'] is True
    assert status['current_state']['strict_target_boundary_passed'] is True
    assert status['current_state']['flag_surface_passed'] is True
    assert status['current_state']['operator_surface_passed'] is True
    assert status['current_state']['performance_passed'] is True
    assert status['current_state']['documentation_passed'] is True
    assert status['current_state']['promotion_target_passed'] is True
    assert status['current_state']['current_package_version'] == '0.3.8'
    assert status['release_assembly']['version_bump_performed'] is True
    assert status['release_assembly']['release_notes_promoted'] is True


def test_phase9i_release_root_contains_final_bundle_set() -> None:
    expected_bundles = {
        'tigrcorn-independent-certification-release-matrix',
        'tigrcorn-same-stack-replay-matrix',
        'tigrcorn-mixed-compatibility-release-matrix',
        'tigrcorn-flag-surface-certification-bundle',
        'tigrcorn-operator-surface-certification-bundle',
        'tigrcorn-performance-certification-bundle',
    }
    actual = {path.name for path in RELEASE_ROOT.iterdir() if path.is_dir()}
    assert expected_bundles.issubset(actual)

    manifest = load_json(RELEASE_ROOT / 'manifest.json')
    assert manifest['source_checkpoint'] == 'phase9i_release_assembly'
    assert manifest['status'] == 'phase9i_release_assembly_certifiably_promotable'
    assert manifest['promotion_ready'] is True
    assert manifest['strict_target_complete'] is True
    for key in ['flag_surface', 'operator_surface', 'performance', 'certification_environment', 'aioquic_adapter_preflight']:
        assert key in manifest['bundles']
    for key in ['flag_surface', 'operator_surface', 'performance']:
        assert manifest['bundles'][key]['release_gate_eligible'] is True

    bundle_index = load_json(RELEASE_ROOT / 'bundle_index.json')
    bundle_summary = load_json(RELEASE_ROOT / 'bundle_summary.json')
    assert bundle_index['source_checkpoint'] == 'phase9i_release_assembly'
    assert bundle_index['promotion_ready'] is True
    assert bundle_index['strict_target_complete'] is True
    assert bundle_index['independent_certification_failed'] == 0
    assert bundle_summary['promotion_ready'] is True
    assert bundle_summary['strict_target_complete'] is True
    assert bundle_summary['independent_certification_failed'] == 0


def test_phase9i_flag_operator_and_performance_bundles_are_current() -> None:
    flag_index = load_json(RELEASE_ROOT / 'tigrcorn-flag-surface-certification-bundle' / 'index.json')
    assert flag_index['public_flag_count'] == 84
    assert flag_index['promotion_ready_count'] == 84
    assert flag_index['hazard_clusters_green'] is True

    operator_index = load_json(RELEASE_ROOT / 'tigrcorn-operator-surface-certification-bundle' / 'index.json')
    assert operator_index['implemented_count'] == 7
    assert operator_index['implemented']['metrics_endpoint'] is True
    assert operator_index['implemented']['workers_process_supervision'] is True

    perf_index = load_json(RELEASE_ROOT / 'tigrcorn-performance-certification-bundle' / 'index.json')
    assert perf_index['profile_count'] == 32
    assert perf_index['lane_counts'] == {'component_regression': 9, 'end_to_end_release': 23}
    current_index = load_json(RELEASE_ROOT / 'tigrcorn-performance-certification-bundle' / 'artifacts' / 'phase6_current_release' / 'index.json')
    assert current_index['passed'] == 32
    assert current_index['failed'] == 0


def test_phase9i_current_gate_truth_matches_live_evaluators() -> None:
    authoritative = evaluate_release_gates(ROOT)
    strict = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion = evaluate_promotion_target(ROOT)
    status = load_json(CONFORMANCE / 'phase9i_release_assembly.current.json')
    release_gate_status = load_json(CONFORMANCE / 'release_gate_status.current.json')
    package_review = load_json(CONFORMANCE / 'package_compliance_review_phase9i.current.json')

    assert status['validation']['evaluate_release_gates_authoritative']['passed'] == authoritative.passed
    assert status['validation']['evaluate_release_gates_strict_target']['passed'] == strict.passed
    assert status['validation']['evaluate_promotion_target']['passed'] == promotion.passed
    assert release_gate_status['passed'] == authoritative.passed
    assert release_gate_status['strict_target_passed'] == strict.passed
    assert release_gate_status['promotion_target_passed'] == promotion.passed
    assert package_review['summary']['current_package_certifiably_fully_featured'] is True
    assert package_review['summary']['remaining_non_passing_independent_scenarios'] == []
    assert authoritative.passed is True
    assert strict.passed is True
    assert promotion.passed is True

    strict_failures = '\n'.join(strict.failures)
    assert strict_failures == ''
