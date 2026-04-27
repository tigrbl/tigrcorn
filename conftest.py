from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PKGS = ROOT / 'pkgs'
if PKGS.is_dir():
    for package_src in sorted(PKGS.glob('*/src'), reverse=True):
        package_src_text = str(package_src)
        if package_src_text not in sys.path:
            sys.path.insert(0, package_src_text)
