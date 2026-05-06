from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates
from tools.ssot_sync import build_registry

ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def test_risk_traceability_graph_is_resolved_and_green():
    claims = _load_json('docs/review/conformance/claims_registry.json')
    registry = build_registry()

    claim_ids = {row['id'] for row in claims['current_and_candidate_claims']}
    risks = registry['risks']
    risk_ids = {row['source_risk_id'] for row in risks}

    assert risk_ids == {
        'R-TRACEABILITY-GOVERNANCE-GAP',
        'R-TEST-STYLE-DRIFT',
        'R-RFC9651-REFERENCE-DRIFT',
        'R-RELEASE-EVIDENCE-RETENTION',
    }
    for row in risks:
        traceability = row['traceability_refs']
        assert set(traceability['claim_refs']) <= claim_ids
        for test_ref in traceability['test_refs']:
            assert (ROOT / test_ref.split('::', 1)[0]).exists()
        for evidence_ref in traceability['evidence_refs']:
            assert (ROOT / evidence_ref).exists()


def test_legacy_unittest_inventory_is_explicit_and_no_unexpected_files_exist():
    inventory = _load_json('LEGACY_UNITTEST_INVENTORY.json')
    assert inventory['forward_runner'] == 'pytest'
    assert inventory['inventory_mode'] == 'grandfathered_legacy_unittest_only'
    assert inventory['unexpected_legacy_files'] == []
    assert set(inventory['detected_legacy_files']) == set(inventory['approved_legacy_files'])


def test_retention_bundles_point_to_existing_release_inputs():
    for relative_path in ('docs/conformance/interop_retention.json', 'docs/conformance/perf_retention.json'):
        rows = _load_json(relative_path)
        assert rows
        for row in rows:
            assert (ROOT / row['path']).exists()


def test_release_gates_consume_governance_graph():
    report = evaluate_release_gates(ROOT)
    assert report.passed, report.failures


def test_governance_scan_passes_for_grandfathered_and_mutable_paths():
    completed = subprocess.run(
        [sys.executable, 'tools/govchk.py', 'scan'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
