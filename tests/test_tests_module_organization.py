from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"


def test_tests_python_files_stay_under_400_lines() -> None:
    oversized = []
    for path in TESTS_ROOT.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 400:
            oversized.append((len(lines), path.relative_to(ROOT).as_posix()))
    assert oversized == []


def test_aioquic_fixture_clients_keep_module_entrypoints() -> None:
    from tests.fixtures_third_party.aioquic_http3_client import main as http3_main
    from tests.fixtures_third_party.aioquic_http3_websocket_client import main as websocket_main

    assert callable(http3_main)
    assert callable(websocket_main)
