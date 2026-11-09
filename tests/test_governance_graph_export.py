from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _ssot_cli_env() -> dict[str, str]:
    env = os.environ.copy()
    local_site_packages = ROOT / ".venv" / "Lib" / "site-packages"
    if local_site_packages.exists():
        existing = env.get("PYTHONPATH")
        parts = [str(local_site_packages)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def test_ssot_graph_export_contains_release_traceability(tmp_path: Path) -> None:
    output_path = tmp_path / "registry.graph.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ssot_registry",
            "graph",
            "export",
            ".",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=_ssot_cli_env(),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    graph = json.loads(output_path.read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in graph["nodes"]}
    edges = {(edge["from"], edge["to"], edge["type"]) for edge in graph["edges"]}

    assert {"feat:governance-graph", "clm:tc-cert-release-gate-graph"} <= node_ids
    assert ("clm:tc-cert-release-gate-graph", "feat:governance-graph", "ASSERTS") in edges
    assert any(
        source == "feat:governance-graph"
        and relation == "COVERED_BY"
        and target.startswith("tst:")
        for source, target, relation in edges
    )
    assert any(
        source.startswith("rsk:")
        and target == "feat:governance-graph"
        and relation == "AFFECTS"
        for source, target, relation in edges
    )
