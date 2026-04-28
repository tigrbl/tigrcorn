import json
from pathlib import Path

from tigrcorn.compat.release_gates import evaluate_promotion_target

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / "docs" / "review" / "conformance"



def test_phase9f3_docs_and_status_exist():
    assert (CONFORMANCE / 'PHASE9F3_CONCURRENCY_WEBSOCKET_KEEPALIVE_CLOSURE.md').exists()
    assert (CONFORMANCE / 'phase9f3_concurrency_keepalive.current.json').exists()
    assert (ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9F3_CONCURRENCY_WEBSOCKET_KEEPALIVE_CLOSURE.md').exists()

    payload = json.loads((CONFORMANCE / 'phase9f3_concurrency_keepalive.current.json').read_text(encoding='utf-8'))
    assert payload['phase'] == '9F3'
    assert payload['checkpoint'] == 'phase9f3_concurrency_keepalive_closure'
    assert payload['current_state']['authoritative_boundary_passed'] is True
    assert payload['current_state']['strict_target_boundary_passed'] is False
    assert payload['current_state']['promotion_target_passed'] is False
    assert payload['current_state']['flag_surface_passed'] is True
    assert payload['current_state']['remaining_flag_runtime_blockers'] == []
    assert '--limit-concurrency' in payload['implemented_flags']

def test_flag_contracts_now_mark_all_rows_promotion_ready():
    payload = json.loads((CONFORMANCE / 'flag_contracts.json').read_text(encoding='utf-8'))
    assert payload['current_state']['promotion_ready_rows'] == payload['public_flag_string_count']
    assert payload['current_state']['runtime_gap_flags'] == []
    rows = {row['flag_strings'][0]: row for row in payload['contracts']}
    for flag in ['--limit-concurrency', '--websocket-ping-interval', '--websocket-ping-timeout']:
        assert rows[flag]['status']['promotion_ready'] is True
        assert rows[flag]['status']['current_runtime_state'] == 'implemented'

def test_phase8_snapshot_and_current_promotion_report_have_green_flag_surface():
    snapshot = json.loads((CONFORMANCE / 'phase8_strict_promotion_target_status.current.json').read_text(encoding='utf-8'))
    assert snapshot['flag_surface_passed'] is True
    assert snapshot['blockers']['flag_surface'] == []
    report = evaluate_promotion_target(ROOT)
    assert report.flag_surface.passed is True
    assert report.flag_surface.failures == []
