from __future__ import annotations

import sys
from pathlib import Path


def ensure_workspace_package_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    package_root = root / "pkgs"
    if not package_root.is_dir():
        return
    for package_src in sorted(package_root.glob("*/src"), reverse=True):
        package_src_text = str(package_src)
        if package_src_text not in sys.path:
            sys.path.insert(0, package_src_text)
