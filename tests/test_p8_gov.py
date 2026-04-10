from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_release_gates

ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def test_risk_traceability_graph_is_resolved_and_green():
    register = _load_json('docs/conformance/risk/RISK_REGISTER.json')
    traceability = _load_json('docs/conformance/risk/RISK_TRACEABILITY.json')
    claims = _load_json('docs/review/conformance/claims_registry.json')

    claim_ids = {row['id'] for row in claims['current_and_candidate_claims']}
    register_ids = {row['risk_id'] for row in register['register']}
    traceability_ids = {row['risk_id'] for row in traceability['risks']}

    assert register_ids == traceability_ids
    assert traceability['structured_fields_bundle'] == 'docs/conformance/sf9651.json'
    for row in traceability['risks']:
        assert set(row['claim_refs']) <= claim_ids
        for test_ref in row['test_refs']:
            assert (ROOT / test_ref.split('::', 1)[0]).exists()
        for evidence_ref in row['evidence_refs']:
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
