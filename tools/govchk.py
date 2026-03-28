from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MARK = "MUT.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_state(path: Path) -> tuple[Path | None, dict[str, Any]]:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    while True:
        marker = current / MARK
        if marker.exists():
            return marker, _load_json(marker)
        if current == ROOT:
            return None, {"state": "unknown"}
        if current.parent == current:
            return None, {"state": "unknown"}
        current = current.parent


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def is_exempt(path: Path, root_cfg: dict[str, Any]) -> bool:
    rel_path = rel(path)
    prefixes = root_cfg.get("legacy_exempt_prefixes", [])
    for prefix in prefixes:
        if rel_path == prefix or rel_path.startswith(prefix):
            return True
    return False


def scan() -> int:
    root_marker = ROOT / MARK
    if not root_marker.exists():
        print("missing root MUT.json")
        return 1
    root_cfg = _load_json(root_marker)
    file_max = int(root_cfg.get("file_name_max", 24))
    folder_max = int(root_cfg.get("folder_name_max", 16))
    path_max = int(root_cfg.get("path_max", 120))

    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        rel_path = rel(path)
        if is_exempt(path, root_cfg):
            continue
        marker, state = resolve_state(path)
        if state.get("state") == "immutable":
            continue
        if len(rel_path) > path_max:
            violations.append(f"path too long ({len(rel_path)}>{path_max}): {rel_path}")
        if path.is_file() and len(path.name) > file_max:
            violations.append(f"file name too long ({len(path.name)}>{file_max}): {rel_path}")
        if path.is_dir() and len(path.name) > folder_max:
            violations.append(f"folder name too long ({len(path.name)}>{folder_max}): {rel_path}")

    if violations:
        print("governance scan failed:")
        for item in violations:
            print(f"- {item}")
        return 1

    print("governance scan passed")
    return 0


def cmd_state(target: str) -> int:
    path = (ROOT / target).resolve() if not os.path.isabs(target) else Path(target).resolve()
    marker, state = resolve_state(path)
    print(json.dumps({
        "target": rel(path),
        "state": state.get("state", "unknown"),
        "marker": rel(marker) if marker is not None else None,
        "reason": state.get("reason"),
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repository governance helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("state", help="Resolve the nearest mutability marker for a path")
    s.add_argument("path")

    sub.add_parser("scan", help="Check naming/path limits for mutable non-exempt paths")
    return parser


def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    if ns.cmd == "state":
        return cmd_state(ns.path)
    if ns.cmd == "scan":
        return scan()
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
