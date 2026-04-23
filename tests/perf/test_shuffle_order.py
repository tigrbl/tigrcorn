from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tigrcorn.compat.perf_runner import load_performance_matrix, run_performance_matrix

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = 'docs/review/performance/performance_matrix.json'


def _default_profile_order(profile_ids: list[str]) -> list[str]:
    matrix = load_performance_matrix(ROOT / MATRIX_PATH)
    return [p.profile_id for p in matrix.profiles if p.profile_id in set(profile_ids)]


def test_same_seed_produces_identical_order():
    profile_ids = ['http11_baseline', 'http11_keepalive', 'ws_http11', 'tls_handshake']
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        s1 = run_performance_matrix(
            ROOT, artifact_root=Path(tmp1) / 'perf', profile_ids=profile_ids,
            establish_baseline=True, shuffle=True, seed=12345,
        )
        s2 = run_performance_matrix(
            ROOT, artifact_root=Path(tmp2) / 'perf', profile_ids=profile_ids,
            establish_baseline=True, shuffle=True, seed=12345,
        )
        assert s1.execution_order == s2.execution_order


def test_shuffle_changes_order():
    profile_ids = ['http11_baseline', 'http11_keepalive', 'ws_http11', 'tls_handshake']
    original_order = _default_profile_order(profile_ids)
    found_different = False
    for seed in range(10):
        with tempfile.TemporaryDirectory() as tmp:
            s = run_performance_matrix(
                ROOT, artifact_root=Path(tmp) / 'perf', profile_ids=profile_ids,
                establish_baseline=True, shuffle=True, seed=seed,
            )
            if s.execution_order != original_order:
                found_different = True
                break
    assert found_different, 'shuffle never produced a different order across 10 seeds'


def test_seed_recorded_in_artifact():
    seed = 99999
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_performance_matrix(
            ROOT, artifact_root=Path(tmp) / 'perf', profile_ids=['http11_baseline'],
            establish_baseline=True, shuffle=True, seed=seed,
        )
        artifact = json.loads((Path(tmp) / 'perf' / 'summary.json').read_text(encoding='utf-8'))
        assert artifact['shuffle']['seed'] == seed
        assert artifact['shuffle']['enabled'] is True
        assert artifact['shuffle']['execution_order'] == [summary.profiles[0].profile_id]


def test_no_shuffle_omits_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_performance_matrix(
            ROOT, artifact_root=Path(tmp) / 'perf', profile_ids=['http11_baseline'],
            establish_baseline=True, shuffle=False,
        )
        assert summary.shuffle_seed is None
        assert summary.execution_order is None
        artifact = json.loads((Path(tmp) / 'perf' / 'summary.json').read_text(encoding='utf-8'))
        assert 'shuffle' not in artifact
